from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .process_transfer_head import _acquire_head_lock, load_process_transfer_head
from .process_transfer_persistence import verify_process_transfer_evidence_bundle


RESTART_STATE = "VERIFIED_LOCAL_PROCESS_TRANSFER_RESTART_EVIDENCE_NO_ACTIVATION"
TRUTH_BOUNDARY = (
    "This gate establishes only restart-time, read-only consistency between an exact caller-expected canonical local "
    "process-transfer head and the exact persisted evidence bundle that head names. Verification runs while holding the "
    "same cooperative local writer-exclusion lock used by head advancement, so cooperating writers cannot advance the "
    "head during this check under the tested local-filesystem scope. It replays the existing receipt/snapshot evidence "
    "and requires exact authority label, sequence, head hash, bundle hash, migration, session and target identities. It "
    "does not prove that the caller's expected head is globally fresh or trusted, authenticate the authority or lock "
    "owner, recover orphaned locks, protect against processes that ignore/delete the lock or adversarially rewrite local "
    "storage, establish distributed/shared-filesystem locking, consensus/fencing/leases, crash or power-loss durability, "
    "launch or replace a process, authorize activation or automatic control, or establish performance, novelty, "
    "scientific-effect, HA/SLA, or production-readiness claims."
)


@dataclass(frozen=True)
class ProcessTransferRestartVerification:
    authority_id: str
    sequence: int
    previous_head_sha256: str
    bundle_sha256: str
    migration_id: str
    session_id: str
    target_candidate_id: str
    head_sha256: str
    exact_expected_head_verified: bool = True
    canonical_head_verified: bool = True
    bundle_evidence_verified: bool = True
    head_bundle_binding_verified: bool = True
    cooperative_writer_exclusion_verified: bool = True
    restart_evidence_verified: bool = True
    automatic_control_allowed: bool = False
    activation_allowed: bool = False
    evidence_state: str = RESTART_STATE
    truth_boundary: str = TRUTH_BOUNDARY


def _require_identity(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or "\n" in value or "\r" in value:
        raise ValueError(f"{field} must be a non-empty single-line string")
    return value


def _require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{field} must be a lowercase SHA-256 hex digest")
    return value


def verify_persisted_process_transfer_restart(
    head_path: str | os.PathLike[str],
    bundle_path: str | os.PathLike[str],
    *,
    expected_authority_id: str,
    expected_sequence: int,
    expected_head_sha256: str,
    expected_migration_id: str,
    expected_session_id: str,
    expected_target_candidate_id: str,
    expected_schema_identity: str,
    expected_codec_identity: str,
    expected_target_artifact_sha256: str,
    expected_verification_manifest_sha256: str,
) -> ProcessTransferRestartVerification:
    """Re-verify an exact persisted local head and its bound evidence bundle without granting activation authority."""

    expected_authority_id = _require_identity(expected_authority_id, "expected_authority_id")
    expected_head_sha256 = _require_sha256(expected_head_sha256, "expected_head_sha256")
    if not isinstance(expected_sequence, int) or isinstance(expected_sequence, bool) or expected_sequence < 1:
        raise ValueError("expected_sequence must be a positive integer")

    target = Path(head_path)
    lock_path = _acquire_head_lock(target)
    try:
        head, head_sha256 = load_process_transfer_head(target)
        if head_sha256 != expected_head_sha256:
            raise ValueError("persisted process-transfer head hash does not match exact expected head")
        if head["authority_id"] != expected_authority_id:
            raise ValueError("persisted process-transfer head authority_id does not match expected authority")
        if head["sequence"] != expected_sequence:
            raise ValueError("persisted process-transfer head sequence does not match expected sequence")
        if head["migration_id"] != expected_migration_id:
            raise ValueError("persisted process-transfer head migration_id does not match expected identity")
        if head["session_id"] != expected_session_id:
            raise ValueError("persisted process-transfer head session_id does not match expected identity")
        if head["target_candidate_id"] != expected_target_candidate_id:
            raise ValueError("persisted process-transfer head target_candidate_id does not match expected identity")

        bundle = verify_process_transfer_evidence_bundle(
            Path(bundle_path).read_bytes(),
            expected_migration_id=expected_migration_id,
            expected_session_id=expected_session_id,
            expected_target_candidate_id=expected_target_candidate_id,
            expected_schema_identity=expected_schema_identity,
            expected_codec_identity=expected_codec_identity,
            expected_target_artifact_sha256=expected_target_artifact_sha256,
            expected_verification_manifest_sha256=expected_verification_manifest_sha256,
        )
        if head["bundle_sha256"] != bundle.bundle_sha256:
            raise ValueError("persisted process-transfer head does not bind the supplied verified evidence bundle")

        return ProcessTransferRestartVerification(
            authority_id=head["authority_id"],
            sequence=head["sequence"],
            previous_head_sha256=head["previous_head_sha256"],
            bundle_sha256=bundle.bundle_sha256,
            migration_id=bundle.migration_id,
            session_id=bundle.session_id,
            target_candidate_id=bundle.target_candidate_id,
            head_sha256=head_sha256,
        )
    finally:
        lock_path.unlink(missing_ok=True)
