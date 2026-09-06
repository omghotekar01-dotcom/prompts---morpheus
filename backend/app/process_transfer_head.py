from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .process_transfer_persistence import verify_process_transfer_evidence_bundle


HEAD_SCHEMA = "morpheus-process-transfer-local-head-v1"
GENESIS_HEAD_SHA256 = "0" * 64
HEAD_STATE = "VERIFIED_LOCAL_MONOTONIC_TRANSFER_HEAD_NO_ACTIVATION"
TRUTH_BOUNDARY = (
    "This gate establishes only a canonical, hash-chained, single-receiver local ordering record for already verified "
    "process-transfer evidence. A caller must present the exact previously observed head hash and the next contiguous "
    "sequence number before the head file is replaced and re-verified. It rejects stale/replayed sequences and stale "
    "compare-and-swap expectations under the tested cooperative single-writer/local-filesystem scope. It does not "
    "authenticate the authority id, protect against an adversary able to rewrite the head file, serialize concurrent "
    "writers across processes, guarantee crash/power-loss durability, establish distributed consensus/fencing/leases, "
    "prove receipt freshness outside this local chain, launch or replace a process, authorize activation or automatic "
    "control, or establish performance, novelty, scientific-effect, HA/SLA, or production-readiness claims."
)


@dataclass(frozen=True)
class ProcessTransferHeadVerification:
    authority_id: str
    sequence: int
    previous_head_sha256: str
    bundle_sha256: str
    migration_id: str
    session_id: str
    target_candidate_id: str
    head_sha256: str
    canonical_head_verified: bool = True
    bundle_evidence_verified: bool = True
    contiguous_sequence_verified: bool = True
    compare_and_swap_verified: bool = True
    automatic_control_allowed: bool = False
    activation_allowed: bool = False
    evidence_state: str = HEAD_STATE
    truth_boundary: str = TRUTH_BOUNDARY


def _require_identity(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or "\n" in value or "\r" in value:
        raise ValueError(f"{field} must be a non-empty single-line string")
    return value


def _require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{field} must be a lowercase SHA-256 hex digest")
    return value


def _canonical_bytes(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")


def _parse_canonical_head(head_bytes: bytes) -> dict[str, Any]:
    if not isinstance(head_bytes, bytes):
        raise TypeError("head_bytes must be bytes")
    try:
        document = json.loads(head_bytes.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("process-transfer head is not valid ASCII JSON") from exc
    if not isinstance(document, dict) or _canonical_bytes(document) != head_bytes:
        raise ValueError("process-transfer head is not canonical JSON")
    expected_keys = {
        "authority_id",
        "bundle_sha256",
        "migration_id",
        "previous_head_sha256",
        "schema",
        "sequence",
        "session_id",
        "target_candidate_id",
    }
    if set(document) != expected_keys:
        raise ValueError("process-transfer head fields do not match schema")
    if document["schema"] != HEAD_SCHEMA:
        raise ValueError("process-transfer head schema mismatch")
    if not isinstance(document["sequence"], int) or isinstance(document["sequence"], bool) or document["sequence"] < 1:
        raise ValueError("process-transfer head sequence must be a positive integer")
    for field in ("authority_id", "migration_id", "session_id", "target_candidate_id"):
        _require_identity(document[field], field)
    _require_sha256(document["previous_head_sha256"], "previous_head_sha256")
    _require_sha256(document["bundle_sha256"], "bundle_sha256")
    return document


def load_process_transfer_head(path: str | os.PathLike[str]) -> tuple[dict[str, Any], str]:
    head_bytes = Path(path).read_bytes()
    document = _parse_canonical_head(head_bytes)
    return document, hashlib.sha256(head_bytes).hexdigest()


def advance_process_transfer_head(
    path: str | os.PathLike[str],
    bundle_path: str | os.PathLike[str],
    *,
    authority_id: str,
    sequence: int,
    expected_previous_head_sha256: str,
    expected_migration_id: str,
    expected_session_id: str,
    expected_target_candidate_id: str,
    expected_schema_identity: str,
    expected_codec_identity: str,
    expected_target_artifact_sha256: str,
    expected_verification_manifest_sha256: str,
) -> ProcessTransferHeadVerification:
    """Advance a cooperative local evidence head with contiguous sequence + explicit CAS semantics."""

    authority_id = _require_identity(authority_id, "authority_id")
    expected_previous_head_sha256 = _require_sha256(expected_previous_head_sha256, "expected_previous_head_sha256")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
        raise ValueError("sequence must be a positive integer")

    target = Path(path)
    parent = target.parent
    if not parent.exists():
        raise FileNotFoundError(f"process-transfer head parent directory does not exist: {parent}")
    if not parent.is_dir():
        raise NotADirectoryError(f"process-transfer head parent is not a directory: {parent}")

    if target.exists():
        current, current_sha256 = load_process_transfer_head(target)
        if current["authority_id"] != authority_id:
            raise ValueError("process-transfer head authority_id does not match expected authority")
        if expected_previous_head_sha256 != current_sha256:
            raise ValueError("stale process-transfer head compare-and-swap expectation")
        if sequence != current["sequence"] + 1:
            raise ValueError("process-transfer head sequence is not the next contiguous value")
    else:
        if expected_previous_head_sha256 != GENESIS_HEAD_SHA256:
            raise ValueError("initial process-transfer head must use genesis previous-head hash")
        if sequence != 1:
            raise ValueError("initial process-transfer head sequence must be 1")

    bundle_bytes = Path(bundle_path).read_bytes()
    bundle = verify_process_transfer_evidence_bundle(
        bundle_bytes,
        expected_migration_id=expected_migration_id,
        expected_session_id=expected_session_id,
        expected_target_candidate_id=expected_target_candidate_id,
        expected_schema_identity=expected_schema_identity,
        expected_codec_identity=expected_codec_identity,
        expected_target_artifact_sha256=expected_target_artifact_sha256,
        expected_verification_manifest_sha256=expected_verification_manifest_sha256,
    )
    document = {
        "authority_id": authority_id,
        "bundle_sha256": bundle.bundle_sha256,
        "migration_id": bundle.migration_id,
        "previous_head_sha256": expected_previous_head_sha256,
        "schema": HEAD_SCHEMA,
        "sequence": sequence,
        "session_id": bundle.session_id,
        "target_candidate_id": bundle.target_candidate_id,
    }
    head_bytes = _canonical_bytes(document)
    head_sha256 = hashlib.sha256(head_bytes).hexdigest()

    fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(head_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise

    persisted, persisted_sha256 = load_process_transfer_head(target)
    if persisted != document or persisted_sha256 != head_sha256:
        raise ValueError("persisted process-transfer head differs from verified staged bytes")

    return ProcessTransferHeadVerification(
        authority_id=authority_id,
        sequence=sequence,
        previous_head_sha256=expected_previous_head_sha256,
        bundle_sha256=bundle.bundle_sha256,
        migration_id=bundle.migration_id,
        session_id=bundle.session_id,
        target_candidate_id=bundle.target_candidate_id,
        head_sha256=head_sha256,
    )
