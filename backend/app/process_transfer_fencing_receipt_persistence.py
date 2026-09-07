from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .process_transfer_fencing_receipt import (
    FencedRestartReceiptVerification,
    verify_fenced_restart_evidence_receipt,
)


EVIDENCE_STATE = "VERIFIED_FENCED_RESTART_RECEIPT_PERSISTED_NO_CUTOVER_AUTHORITY"
TRUTH_BOUNDARY = (
    "This gate persists only an already-canonical fenced restart evidence receipt after exact identity replay, then "
    "re-reads and replays the exact persisted bytes. The implementation uses a same-directory temporary file, file-level "
    "fsync and os.replace where the host filesystem honors those semantics. It does not repeat the external fencing "
    "compare-and-advance operation, prove the fencing generation is still current, authenticate or attest the external "
    "fencing service, atomically snapshot the separately persisted head/bundle, provide leases/consensus/distributed "
    "locking, guarantee directory-entry or power-loss durability, perform live process replacement, authorize activation "
    "or traffic switching, or establish benchmark, novelty, scientific-effect, HA/SLA or production-readiness claims."
)


@dataclass(frozen=True)
class FencedRestartReceiptPersistenceEvidence:
    path: str
    receipt_sha256: str
    receipt_size_bytes: int
    key_id: str
    authority_id: str
    sequence: int
    head_sha256: str
    bundle_sha256: str
    fencing_authority_id: str
    previous_fencing_counter: int
    fencing_counter: int
    pre_write_replay_verified: bool = True
    file_fsync_completed: bool = True
    atomic_name_replace_completed: bool = True
    post_write_replay_verified: bool = True
    automatic_control_allowed: bool = False
    activation_allowed: bool = False
    traffic_switching_allowed: bool = False
    evidence_state: str = EVIDENCE_STATE
    truth_boundary: str = TRUTH_BOUNDARY


def _require_bytes(value: Any, field: str) -> bytes:
    if not isinstance(value, bytes):
        raise TypeError(f"{field} must be bytes")
    return value


def _verification_kwargs(
    *,
    expected_key_id: str,
    expected_authority_id: str,
    expected_sequence: int,
    expected_head_sha256: str,
    expected_bundle_sha256: str,
    expected_migration_id: str,
    expected_session_id: str,
    expected_target_candidate_id: str,
    expected_fencing_authority_id: str,
    expected_previous_fencing_counter: int,
    expected_fencing_counter: int,
) -> dict[str, object]:
    return {
        "expected_key_id": expected_key_id,
        "expected_authority_id": expected_authority_id,
        "expected_sequence": expected_sequence,
        "expected_head_sha256": expected_head_sha256,
        "expected_bundle_sha256": expected_bundle_sha256,
        "expected_migration_id": expected_migration_id,
        "expected_session_id": expected_session_id,
        "expected_target_candidate_id": expected_target_candidate_id,
        "expected_fencing_authority_id": expected_fencing_authority_id,
        "expected_previous_fencing_counter": expected_previous_fencing_counter,
        "expected_fencing_counter": expected_fencing_counter,
    }


def persist_fenced_restart_evidence_receipt(
    path: str | os.PathLike[str],
    receipt_bytes: bytes,
    *,
    expected_key_id: str,
    expected_authority_id: str,
    expected_sequence: int,
    expected_head_sha256: str,
    expected_bundle_sha256: str,
    expected_migration_id: str,
    expected_session_id: str,
    expected_target_candidate_id: str,
    expected_fencing_authority_id: str,
    expected_previous_fencing_counter: int,
    expected_fencing_counter: int,
) -> FencedRestartReceiptPersistenceEvidence:
    """Replay exact receipt identity before write, replace locally, then replay exact persisted bytes."""

    receipt_bytes = _require_bytes(receipt_bytes, "receipt_bytes")
    kwargs = _verification_kwargs(
        expected_key_id=expected_key_id,
        expected_authority_id=expected_authority_id,
        expected_sequence=expected_sequence,
        expected_head_sha256=expected_head_sha256,
        expected_bundle_sha256=expected_bundle_sha256,
        expected_migration_id=expected_migration_id,
        expected_session_id=expected_session_id,
        expected_target_candidate_id=expected_target_candidate_id,
        expected_fencing_authority_id=expected_fencing_authority_id,
        expected_previous_fencing_counter=expected_previous_fencing_counter,
        expected_fencing_counter=expected_fencing_counter,
    )
    before = verify_fenced_restart_evidence_receipt(receipt_bytes, **kwargs)

    target = Path(path)
    parent = target.parent
    if not parent.exists():
        raise FileNotFoundError(f"fenced restart receipt parent directory does not exist: {parent}")
    if not parent.is_dir():
        raise NotADirectoryError(f"fenced restart receipt parent is not a directory: {parent}")

    fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(receipt_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        finally:
            raise

    persisted = target.read_bytes()
    after = verify_fenced_restart_evidence_receipt(persisted, **kwargs)
    expected_hash = hashlib.sha256(receipt_bytes).hexdigest()
    if persisted != receipt_bytes or before.receipt_sha256 != expected_hash or after.receipt_sha256 != expected_hash:
        raise ValueError("persisted fenced restart receipt bytes differ from verified staged bytes")

    return FencedRestartReceiptPersistenceEvidence(
        path=str(target),
        receipt_sha256=after.receipt_sha256,
        receipt_size_bytes=after.receipt_size_bytes,
        key_id=after.key_id,
        authority_id=after.authority_id,
        sequence=after.sequence,
        head_sha256=after.head_sha256,
        bundle_sha256=after.bundle_sha256,
        fencing_authority_id=after.fencing_authority_id,
        previous_fencing_counter=after.previous_fencing_counter,
        fencing_counter=after.fencing_counter,
    )


def load_fenced_restart_evidence_receipt(
    path: str | os.PathLike[str],
    *,
    expected_key_id: str,
    expected_authority_id: str,
    expected_sequence: int,
    expected_head_sha256: str,
    expected_bundle_sha256: str,
    expected_migration_id: str,
    expected_session_id: str,
    expected_target_candidate_id: str,
    expected_fencing_authority_id: str,
    expected_previous_fencing_counter: int,
    expected_fencing_counter: int,
) -> FencedRestartReceiptVerification:
    """Read persisted receipt bytes and replay the complete canonical exact-identity gate."""

    return verify_fenced_restart_evidence_receipt(
        Path(path).read_bytes(),
        **_verification_kwargs(
            expected_key_id=expected_key_id,
            expected_authority_id=expected_authority_id,
            expected_sequence=expected_sequence,
            expected_head_sha256=expected_head_sha256,
            expected_bundle_sha256=expected_bundle_sha256,
            expected_migration_id=expected_migration_id,
            expected_session_id=expected_session_id,
            expected_target_candidate_id=expected_target_candidate_id,
            expected_fencing_authority_id=expected_fencing_authority_id,
            expected_previous_fencing_counter=expected_previous_fencing_counter,
            expected_fencing_counter=expected_fencing_counter,
        ),
    )
