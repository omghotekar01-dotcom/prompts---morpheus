from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Mapping

from .schema_identity import GENERATED_RECORD_SCHEMA_PREFIX


IDENTIFIED_SNAPSHOT_MAGIC = b"MORPHEUS_IDENTIFIED_LOGICAL_INDEX_SNAPSHOT_V1"
LOGICAL_SNAPSHOT_MAGIC = b"MORPHEUS_LOGICAL_INDEX_SNAPSHOT_V1"
MAX_IDENTITY_BYTES = 4096
MAX_SNAPSHOT_BYTES = 256 * 1024 * 1024
MAX_RECORDS = 1_000_000
MAX_RECORD_BYTES = 16 * 1024 * 1024
MAX_TOTAL_RECORD_BYTES = 256 * 1024 * 1024
_SCHEMA_RE = re.compile(r"^morpheus-record-schema-v1:[0-9a-f]{64}$")
_HEX64_RE = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True)
class SnapshotInspection:
    schema_identity: str
    codec_identity: str
    record_count: int
    total_record_bytes: int
    snapshot_sha256: str
    snapshot_size_bytes: int


@dataclass(frozen=True)
class ProcessTransferAdmission:
    migration_id: str
    session_id: str
    source_candidate_id: str
    target_candidate_id: str
    schema_identity: str
    codec_identity: str
    snapshot_sha256: str
    snapshot_size_bytes: int
    record_count: int
    total_record_bytes: int
    target_artifact_sha256: str
    verification_manifest_sha256: str
    automatic_control_allowed: bool = False
    activation_allowed: bool = False
    evidence_state: str = "VERIFIED_LOGICAL_PROCESS_TRANSFER_ADMITTED_NO_ACTIVATION"
    truth_boundary: str = (
        "Compatibility and byte-structure admission only: no record decoding, native-memory restoration, "
        "live process swap, freshness/authenticity proof, rollback prevention, or production authorization."
    )


def _parse_size(line: bytes, field_name: str) -> int:
    if not line or any(byte < 48 or byte > 57 for byte in line):
        raise ValueError(f"snapshot {field_name} is not an unsigned decimal integer")
    return int(line)


def _read_line(data: bytes, offset: int, field_name: str) -> tuple[bytes, int]:
    end = data.find(b"\n", offset)
    if end < 0:
        raise ValueError(f"snapshot is missing {field_name}")
    return data[offset:end], end + 1


def _read_framed_field(
    data: bytes,
    offset: int,
    *,
    max_bytes: int,
    field_name: str,
) -> tuple[bytes, int]:
    size_line, offset = _read_line(data, offset, f"{field_name} length")
    size = _parse_size(size_line, f"{field_name} length")
    if size > max_bytes:
        raise ValueError(f"snapshot {field_name} exceeds limit")
    end = offset + size
    if end > len(data):
        raise ValueError(f"snapshot {field_name} is truncated")
    value = data[offset:end]
    if end >= len(data) or data[end] != 10:
        raise ValueError(f"snapshot {field_name} delimiter is invalid")
    return value, end + 1


def _expected_identity_bytes(value: str, field_name: str) -> bytes:
    if not value:
        raise ValueError(f"expected {field_name} must not be empty")
    encoded = value.encode("utf-8")
    if len(encoded) > MAX_IDENTITY_BYTES:
        raise ValueError(f"expected {field_name} exceeds limit")
    return encoded


def _inspect_logical_snapshot(payload: bytes) -> tuple[int, int]:
    offset = 0
    magic, offset = _read_line(payload, offset, "logical snapshot magic")
    if magic != LOGICAL_SNAPSHOT_MAGIC:
        raise ValueError("logical snapshot magic mismatch")

    count_line, offset = _read_line(payload, offset, "record count")
    record_count = _parse_size(count_line, "record count")
    if record_count > MAX_RECORDS:
        raise ValueError("logical snapshot exceeds record-count limit")

    total = 0
    for _ in range(record_count):
        size_line, offset = _read_line(payload, offset, "record length")
        size = _parse_size(size_line, "record length")
        if size > MAX_RECORD_BYTES:
            raise ValueError("logical snapshot record exceeds per-record limit")
        if total > MAX_TOTAL_RECORD_BYTES or size > MAX_TOTAL_RECORD_BYTES - total:
            raise ValueError("logical snapshot exceeds total payload limit")
        end = offset + size
        if end > len(payload):
            raise ValueError("logical snapshot record is truncated")
        if end >= len(payload) or payload[end] != 10:
            raise ValueError("logical snapshot record delimiter is invalid")
        total += size
        offset = end + 1

    if offset != len(payload):
        raise ValueError("logical snapshot contains trailing bytes")
    return record_count, total


def inspect_identified_snapshot(
    snapshot_bytes: bytes,
    *,
    expected_schema_identity: str,
    expected_codec_identity: str,
) -> SnapshotInspection:
    """Validate the C++ identified snapshot envelope without decoding any Record."""

    if not isinstance(snapshot_bytes, bytes):
        raise TypeError("snapshot_bytes must be bytes")
    expected_schema = _expected_identity_bytes(expected_schema_identity, "schema identity")
    expected_codec = _expected_identity_bytes(expected_codec_identity, "codec identity")

    offset = 0
    magic, offset = _read_line(snapshot_bytes, offset, "identified snapshot magic")
    if magic != IDENTIFIED_SNAPSHOT_MAGIC:
        raise ValueError("identified snapshot magic mismatch")

    schema, offset = _read_framed_field(
        snapshot_bytes, offset, max_bytes=MAX_IDENTITY_BYTES, field_name="schema identity"
    )
    codec, offset = _read_framed_field(
        snapshot_bytes, offset, max_bytes=MAX_IDENTITY_BYTES, field_name="codec identity"
    )
    if schema != expected_schema:
        raise ValueError("snapshot schema identity mismatch")
    if codec != expected_codec:
        raise ValueError("snapshot codec identity mismatch")

    payload, offset = _read_framed_field(
        snapshot_bytes, offset, max_bytes=MAX_SNAPSHOT_BYTES, field_name="snapshot payload"
    )
    if offset != len(snapshot_bytes):
        raise ValueError("identified snapshot contains trailing bytes")

    record_count, total_record_bytes = _inspect_logical_snapshot(payload)
    return SnapshotInspection(
        schema_identity=expected_schema_identity,
        codec_identity=expected_codec_identity,
        record_count=record_count,
        total_record_bytes=total_record_bytes,
        snapshot_sha256=hashlib.sha256(snapshot_bytes).hexdigest(),
        snapshot_size_bytes=len(snapshot_bytes),
    )


def _require_hex_digest(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or _HEX64_RE.fullmatch(value) is None:
        raise ValueError(f"verified migration {field_name} must be a 64-character hexadecimal digest")
    return value.lower()


def _require_generated_schema_identity(value: str, field_name: str) -> None:
    if not value.startswith(GENERATED_RECORD_SCHEMA_PREFIX) or _SCHEMA_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} is not a canonical generated-record schema identity")


def admit_verified_process_transfer(
    migration: Mapping[str, Any],
    snapshot_bytes: bytes,
    *,
    source_schema_identity: str,
    target_schema_identity: str,
    codec_identity: str,
) -> ProcessTransferAdmission:
    """Bind inspected snapshot bytes to an already VERIFIED migration.

    The returned value is intentionally non-executing. It does not call commit(),
    mutate a data plane, decode records, launch a worker, or authorize automatic
    control. A later explicit operation must still reconstruct/validate the target
    and separately satisfy activation policy.
    """

    if migration.get("state") != "VERIFIED":
        raise ValueError("process transfer requires migration state VERIFIED")
    if migration.get("compile_verified") is not True or migration.get("correctness_verified") is not True:
        raise ValueError("process transfer requires compile and correctness verification")

    _require_generated_schema_identity(source_schema_identity, "source_schema_identity")
    _require_generated_schema_identity(target_schema_identity, "target_schema_identity")
    if source_schema_identity != target_schema_identity:
        raise ValueError("source and target generated record schemas are incompatible")
    _expected_identity_bytes(codec_identity, "codec identity")

    migration_id = migration.get("migration_id")
    session_id = migration.get("session_id")
    source_candidate_id = migration.get("from_candidate_id")
    target_candidate_id = migration.get("to_candidate_id")
    for value, field_name in (
        (migration_id, "migration_id"),
        (session_id, "session_id"),
        (source_candidate_id, "from_candidate_id"),
        (target_candidate_id, "to_candidate_id"),
    ):
        if not isinstance(value, str) or not value:
            raise ValueError(f"verified migration {field_name} is required")
    if source_candidate_id == target_candidate_id:
        raise ValueError("verified migration source and target candidates must differ")

    target_artifact_sha256 = _require_hex_digest(migration.get("artifact_sha256"), "artifact_sha256")
    verification_manifest_sha256 = _require_hex_digest(
        migration.get("verification_manifest_sha256"), "verification_manifest_sha256"
    )
    inspection = inspect_identified_snapshot(
        snapshot_bytes,
        expected_schema_identity=source_schema_identity,
        expected_codec_identity=codec_identity,
    )

    return ProcessTransferAdmission(
        migration_id=migration_id,
        session_id=session_id,
        source_candidate_id=source_candidate_id,
        target_candidate_id=target_candidate_id,
        schema_identity=source_schema_identity,
        codec_identity=codec_identity,
        snapshot_sha256=inspection.snapshot_sha256,
        snapshot_size_bytes=inspection.snapshot_size_bytes,
        record_count=inspection.record_count,
        total_record_bytes=inspection.total_record_bytes,
        target_artifact_sha256=target_artifact_sha256,
        verification_manifest_sha256=verification_manifest_sha256,
    )
