from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from .process_transfer import ProcessTransferAdmission, inspect_identified_snapshot


RECEIPT_SCHEMA = "morpheus.process-transfer-admission-receipt.v1"
EVIDENCE_STATE = "VERIFIED_PROCESS_TRANSFER_ADMISSION_RECEIPT_REPLAYED_NO_ACTIVATION"
TRUTH_BOUNDARY = (
    "Canonical receipt replay proves only that supplied receipt bytes are an exact canonical encoding of a "
    "non-authoritative ProcessTransferAdmission and that the supplied snapshot bytes and caller-supplied target "
    "identities match that receipt during this call. It does not authenticate receipt origin, establish freshness "
    "or latest-head truth, prevent coordinated rollback/replay, decode records, restore native memory, launch or "
    "replace a process, authorize activation, provide fencing/leases/consensus/HA, prove crash durability, or establish "
    "production readiness, benchmark performance, novelty, or automatic-control authority."
)

_FIELDS = (
    "schema",
    "migration_id",
    "session_id",
    "source_candidate_id",
    "target_candidate_id",
    "schema_identity",
    "codec_identity",
    "snapshot_sha256",
    "snapshot_size_bytes",
    "record_count",
    "total_record_bytes",
    "target_artifact_sha256",
    "verification_manifest_sha256",
    "automatic_control_allowed",
    "activation_allowed",
    "admission_evidence_state",
)
_HEX_FIELDS = ("snapshot_sha256", "target_artifact_sha256", "verification_manifest_sha256")
_TEXT_FIELDS = (
    "migration_id",
    "session_id",
    "source_candidate_id",
    "target_candidate_id",
    "schema_identity",
    "codec_identity",
    "admission_evidence_state",
)


@dataclass(frozen=True)
class ProcessTransferReceiptVerification:
    receipt_sha256: str
    receipt_size_bytes: int
    snapshot_sha256: str
    snapshot_size_bytes: int
    migration_id: str
    session_id: str
    target_candidate_id: str
    target_artifact_sha256: str
    verification_manifest_sha256: str
    canonical_encoding_verified: bool = True
    snapshot_identity_verified: bool = True
    target_binding_verified: bool = True
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False
    activation_allowed: bool = False
    truth_boundary: str = TRUTH_BOUNDARY


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _require_nonempty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"receipt {field} must be a non-empty string")
    return value


def _require_nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"receipt {field} must be a non-negative integer")
    return value


def _require_sha256(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value.lower() != value
        or any(ch not in "0123456789abcdef" for ch in value)
    ):
        raise ValueError(f"receipt {field} must be 64 lowercase hexadecimal characters")
    return value


def _payload_from_admission(admission: ProcessTransferAdmission) -> dict[str, Any]:
    if not isinstance(admission, ProcessTransferAdmission):
        raise TypeError("admission must be ProcessTransferAdmission")
    if admission.automatic_control_allowed is not False or admission.activation_allowed is not False:
        raise ValueError("process-transfer admission receipt cannot encode activation or automatic-control authority")

    payload = {
        "schema": RECEIPT_SCHEMA,
        "migration_id": admission.migration_id,
        "session_id": admission.session_id,
        "source_candidate_id": admission.source_candidate_id,
        "target_candidate_id": admission.target_candidate_id,
        "schema_identity": admission.schema_identity,
        "codec_identity": admission.codec_identity,
        "snapshot_sha256": admission.snapshot_sha256,
        "snapshot_size_bytes": admission.snapshot_size_bytes,
        "record_count": admission.record_count,
        "total_record_bytes": admission.total_record_bytes,
        "target_artifact_sha256": admission.target_artifact_sha256,
        "verification_manifest_sha256": admission.verification_manifest_sha256,
        "automatic_control_allowed": False,
        "activation_allowed": False,
        "admission_evidence_state": admission.evidence_state,
    }
    _validate_payload(payload)
    return payload


def _validate_payload(payload: Mapping[str, Any]) -> None:
    if set(payload) != set(_FIELDS):
        missing = sorted(set(_FIELDS) - set(payload))
        extra = sorted(set(payload) - set(_FIELDS))
        raise ValueError(f"receipt schema fields mismatch: missing={missing}, extra={extra}")
    if payload.get("schema") != RECEIPT_SCHEMA:
        raise ValueError("receipt schema identity mismatch")
    for field in _TEXT_FIELDS:
        _require_nonempty_text(payload.get(field), field)
    for field in _HEX_FIELDS:
        _require_sha256(payload.get(field), field)
    for field in ("snapshot_size_bytes", "record_count", "total_record_bytes"):
        _require_nonnegative_int(payload.get(field), field)
    if payload.get("automatic_control_allowed") is not False:
        raise ValueError("receipt must not grant automatic-control authority")
    if payload.get("activation_allowed") is not False:
        raise ValueError("receipt must not grant activation authority")


def encode_process_transfer_admission_receipt(admission: ProcessTransferAdmission) -> bytes:
    """Encode an admitted logical process transfer as strict canonical JSON bytes."""

    return _canonical_bytes(_payload_from_admission(admission))


def verify_process_transfer_admission_receipt(
    receipt_bytes: bytes,
    snapshot_bytes: bytes,
    *,
    expected_migration_id: str,
    expected_session_id: str,
    expected_target_candidate_id: str,
    expected_schema_identity: str,
    expected_codec_identity: str,
    expected_target_artifact_sha256: str,
    expected_verification_manifest_sha256: str,
) -> ProcessTransferReceiptVerification:
    """Replay a canonical admission receipt against exact bytes and expected target identities."""

    if not isinstance(receipt_bytes, bytes):
        raise TypeError("receipt_bytes must be bytes")
    try:
        decoded = receipt_bytes.decode("utf-8")
        payload = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("receipt is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("receipt root must be an object")
    _validate_payload(payload)
    if _canonical_bytes(payload) != receipt_bytes:
        raise ValueError("receipt bytes are not canonical")

    expected_values = {
        "migration_id": _require_nonempty_text(expected_migration_id, "expected migration_id"),
        "session_id": _require_nonempty_text(expected_session_id, "expected session_id"),
        "target_candidate_id": _require_nonempty_text(expected_target_candidate_id, "expected target_candidate_id"),
        "schema_identity": _require_nonempty_text(expected_schema_identity, "expected schema_identity"),
        "codec_identity": _require_nonempty_text(expected_codec_identity, "expected codec_identity"),
        "target_artifact_sha256": _require_sha256(expected_target_artifact_sha256, "expected target_artifact_sha256"),
        "verification_manifest_sha256": _require_sha256(
            expected_verification_manifest_sha256, "expected verification_manifest_sha256"
        ),
    }
    for field, expected in expected_values.items():
        if payload[field] != expected:
            raise ValueError(f"receipt {field} does not match expected identity")

    inspection = inspect_identified_snapshot(
        snapshot_bytes,
        expected_schema_identity=expected_schema_identity,
        expected_codec_identity=expected_codec_identity,
    )
    observed = {
        "snapshot_sha256": inspection.snapshot_sha256,
        "snapshot_size_bytes": inspection.snapshot_size_bytes,
        "record_count": inspection.record_count,
        "total_record_bytes": inspection.total_record_bytes,
    }
    for field, value in observed.items():
        if payload[field] != value:
            raise ValueError(f"receipt {field} does not match supplied snapshot bytes")

    return ProcessTransferReceiptVerification(
        receipt_sha256=hashlib.sha256(receipt_bytes).hexdigest(),
        receipt_size_bytes=len(receipt_bytes),
        snapshot_sha256=inspection.snapshot_sha256,
        snapshot_size_bytes=inspection.snapshot_size_bytes,
        migration_id=payload["migration_id"],
        session_id=payload["session_id"],
        target_candidate_id=payload["target_candidate_id"],
        target_artifact_sha256=payload["target_artifact_sha256"],
        verification_manifest_sha256=payload["verification_manifest_sha256"],
    )
