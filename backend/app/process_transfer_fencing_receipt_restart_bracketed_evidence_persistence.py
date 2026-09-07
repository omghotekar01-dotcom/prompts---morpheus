from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .process_transfer_fencing_receipt_restart_bracketed_evidence import (
    BracketedRestartObservationReceiptVerification,
    verify_bracketed_restart_observation_receipt,
)


EVIDENCE_STATE = "VERIFIED_BRACKETED_RESTART_OBSERVATION_RECEIPT_PERSISTED_NO_CUTOVER_AUTHORITY"
TRUTH_BOUNDARY = (
    "This gate persists only an already-canonical bracketed restart-observation receipt after exact identity replay, then "
    "re-reads and replays the exact persisted bytes. The implementation uses a same-directory temporary file, file-level "
    "fsync and os.replace where the host filesystem honors those semantics. Persistence records historical evidence only: "
    "it does not call the external fencing authority, repeat either fencing-counter observation, re-run local head/bundle "
    "verification, prove the fencing generation is current, prove it stayed unchanged between observations or after return, "
    "or establish an atomic snapshot, lease, lock, consensus or safe cutover. It does not atomically snapshot separately "
    "persisted head/bundle state, guarantee directory-entry or power-loss durability, perform live process replacement, "
    "authorize activation, automatic control or traffic switching, or establish benchmark, performance, novelty, "
    "scientific-effect, HA/SLA or production-readiness claims."
)


@dataclass(frozen=True)
class BracketedRestartObservationReceiptPersistenceEvidence:
    path: str
    evidence_receipt_sha256: str
    evidence_receipt_size_bytes: int
    source_receipt_sha256: str
    key_id: str
    authority_id: str
    sequence: int
    head_sha256: str
    bundle_sha256: str
    fencing_authority_id: str
    previous_fencing_counter: int
    fencing_counter: int
    observed_fencing_counter_before: int
    observed_fencing_counter_after: int
    pre_write_replay_verified: bool = True
    file_fsync_completed: bool = True
    atomic_name_replace_completed: bool = True
    post_write_replay_verified: bool = True
    historical_observation_binding_only: bool = True
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
    expected_source_receipt_sha256: str,
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
        "expected_source_receipt_sha256": expected_source_receipt_sha256,
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


def persist_bracketed_restart_observation_receipt(
    path: str | os.PathLike[str],
    receipt_bytes: bytes,
    *,
    expected_source_receipt_sha256: str,
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
) -> BracketedRestartObservationReceiptPersistenceEvidence:
    """Replay exact historical receipt identity before and after local staged replacement."""

    receipt_bytes = _require_bytes(receipt_bytes, "receipt_bytes")
    kwargs = _verification_kwargs(
        expected_source_receipt_sha256=expected_source_receipt_sha256,
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
    before = verify_bracketed_restart_observation_receipt(receipt_bytes, **kwargs)

    target = Path(path)
    parent = target.parent
    if not parent.exists():
        raise FileNotFoundError(f"bracketed restart observation receipt parent directory does not exist: {parent}")
    if not parent.is_dir():
        raise NotADirectoryError(f"bracketed restart observation receipt parent is not a directory: {parent}")

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
    after = verify_bracketed_restart_observation_receipt(persisted, **kwargs)
    expected_hash = hashlib.sha256(receipt_bytes).hexdigest()
    if (
        persisted != receipt_bytes
        or before.evidence_receipt_sha256 != expected_hash
        or after.evidence_receipt_sha256 != expected_hash
    ):
        raise ValueError("persisted bracketed restart observation receipt bytes differ from verified staged bytes")

    return BracketedRestartObservationReceiptPersistenceEvidence(
        path=str(target),
        evidence_receipt_sha256=after.evidence_receipt_sha256,
        evidence_receipt_size_bytes=after.evidence_receipt_size_bytes,
        source_receipt_sha256=after.source_receipt_sha256,
        key_id=after.key_id,
        authority_id=after.authority_id,
        sequence=after.sequence,
        head_sha256=after.head_sha256,
        bundle_sha256=after.bundle_sha256,
        fencing_authority_id=after.fencing_authority_id,
        previous_fencing_counter=after.previous_fencing_counter,
        fencing_counter=after.fencing_counter,
        observed_fencing_counter_before=after.observed_fencing_counter_before,
        observed_fencing_counter_after=after.observed_fencing_counter_after,
    )


def load_bracketed_restart_observation_receipt(
    path: str | os.PathLike[str],
    *,
    expected_source_receipt_sha256: str,
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
) -> BracketedRestartObservationReceiptVerification:
    """Read persisted bytes and replay the canonical exact-identity historical-evidence gate."""

    return verify_bracketed_restart_observation_receipt(
        Path(path).read_bytes(),
        **_verification_kwargs(
            expected_source_receipt_sha256=expected_source_receipt_sha256,
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
