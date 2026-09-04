"""Bind cooperative P68 serialization to the exact lock instance created by this attempt.

P70 tightens one narrow local-filesystem seam left explicit by P69. P69 proves that
cooperating writers using one O_CREAT|O_EXCL lock path serialize advancement attempts,
but it does not bind lock release to the exact lock-file contents created by the
current attempt. P70 writes a fresh high-entropy ownership token after exclusive
creation, executes P68, then re-reads the lock and unlinks it only when its exact bytes
still match this attempt.

The token is local coordination material, not an authentication credential. Only its
SHA-256 digest is returned in evidence. This remains a cooperative local protocol:
writers that bypass the gate are not excluded, stale locks are not stolen, and a
process crash can leave a lock behind. If an external actor replaces the lock after
P68 has already published the successor, P70 fails closed and leaves that replacement
lock untouched; it cannot roll back the already-completed P68 publication.
"""
from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

from .dataplane_recovery_anchor_advance import (
    EVIDENCE_STATE as P68_EVIDENCE_STATE,
    RecoveryExpectedHeadAdvanceEvidence,
    advance_recovery_expected_head,
)
from .dataplane_recovery_anchor_rebootstrap import RecoveryStoredExpectedHeadEvidence
from .dataplane_recovery_anchor_store import RecoveryExpectedHeadStoreEvidence

EVIDENCE_STATE = "LOCAL_DATA_PLANE_RECOVERY_EXPECTED_HEAD_OWNERSHIP_BOUND_SERIALIZATION_VERIFIED"
TRUTH_BOUNDARY = (
    "This gate proves only that one P68 advancement executed after this process exclusively created a caller-selected "
    "same-directory cooperative lock, that a fresh per-attempt token was written and fsynced to that lock, and that release "
    "occurred only after the exact lock bytes were re-read and matched this attempt. Only the token SHA-256 is retained as "
    "evidence. It does not authenticate process identity or make the token a security credential. Writers bypassing P70 are "
    "not excluded; stale locks are not stolen; process crashes can leave locks behind; and filesystem semantics remain those "
    "of the selected OS/filesystem. If the lock is replaced after P68 has already published, this gate can detect the "
    "disturbance and preserve the replacement lock but cannot roll back that P68 publication. It establishes no universal "
    "CAS, lease, fencing token, starvation freedom, global latest-head knowledge, rollback resistance, TPM/HSM protection, "
    "remote witnessing, distributed consensus, HA, native-object recovery, cross-process hot swap, production readiness, "
    "benchmark performance, or automatic-control authority."
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _default_lock_path(target: Path) -> Path:
    return target.with_name(f".{target.name}.morpheus-head-advance.lock")


@dataclass(frozen=True)
class RecoveryExpectedHeadOwnershipBoundAdvanceEvidence:
    sequence: int
    lineage_sha256: str
    anchor_payload_sha256: str
    anchor_payload_size_bytes: int
    predecessor_sequence: int
    predecessor_lineage_sha256: str
    lock_path: str
    ownership_token_sha256: str
    exclusive_create_used: bool
    ownership_token_fsynced: bool
    p68_executed_under_lock: bool
    lock_identity_rechecked: bool
    ownership_bound_release_verified: bool
    advancement_verified: bool
    p68_evidence_state: str
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def advance_recovery_expected_head_ownership_bound(
    path: str | os.PathLike[str],
    predecessor_store_evidence: RecoveryExpectedHeadStoreEvidence,
    recovery_evidence: RecoveryStoredExpectedHeadEvidence,
    *,
    lock_path: str | os.PathLike[str] | None = None,
) -> RecoveryExpectedHeadOwnershipBoundAdvanceEvidence:
    """Run one P68 advancement while owning and identity-checking one lock instance."""
    target = Path(path)
    if not target.name:
        raise ValueError("recovery expected-head store path must name a file")

    lock = Path(lock_path) if lock_path is not None else _default_lock_path(target)
    if not lock.name:
        raise ValueError("recovery expected-head lock path must name a file")
    if lock.parent.resolve() != target.parent.resolve():
        raise ValueError("P70 lock path must be in the same directory as the expected-head anchor")
    if lock == target:
        raise ValueError("P70 lock path must differ from the expected-head anchor path")

    lock.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_bytes(32)
    lock_bytes = b"morpheus-p70-owner-v1:" + token.hex().encode("ascii") + b"\n"
    descriptor: int | None = None
    lock_owned = False
    advancement: RecoveryExpectedHeadAdvanceEvidence | None = None
    identity_rechecked = False

    try:
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise RuntimeError("P70 cooperative advancement lock already exists; refusing unsafe lock stealing") from exc

        lock_owned = True
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = None
            handle.write(lock_bytes)
            handle.flush()
            os.fsync(handle.fileno())

        advancement = advance_recovery_expected_head(path, predecessor_store_evidence, recovery_evidence)
        if advancement.evidence_state != P68_EVIDENCE_STATE:
            raise ValueError("P68 advancement evidence has an incompatible evidence state")
        if not advancement.predecessor_identity_rechecked:
            raise ValueError("P68 advancement did not recheck predecessor identity")
        if not advancement.exact_p67_successor_bound:
            raise ValueError("P68 advancement is not bound to the exact P67 successor")
        if not advancement.readback_identity_verified or not advancement.advancement_consistency_verified:
            raise ValueError("P68 advancement is not readback/consistency verified")
        if advancement.automatic_control_allowed:
            raise ValueError("P68 advancement cannot authorize automatic control")

        try:
            current_lock_bytes = lock.read_bytes()
        except FileNotFoundError as exc:
            lock_owned = False
            raise RuntimeError("P70 lock disappeared before ownership-bound release") from exc
        if current_lock_bytes != lock_bytes:
            lock_owned = False
            raise RuntimeError("P70 lock identity changed before release; refusing to unlink a foreign lock")
        identity_rechecked = True
        lock.unlink()
        lock_owned = False
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if lock_owned:
            try:
                if lock.read_bytes() == lock_bytes:
                    lock.unlink()
            except FileNotFoundError:
                pass

    if advancement is None:
        raise RuntimeError("P70 advancement completed without P68 evidence")
    if not identity_rechecked:
        raise RuntimeError("P70 advancement completed without lock identity recheck")
    if lock.exists():
        raise RuntimeError("P70 ownership-bound cooperative lock was not released")

    return RecoveryExpectedHeadOwnershipBoundAdvanceEvidence(
        sequence=advancement.sequence,
        lineage_sha256=advancement.lineage_sha256,
        anchor_payload_sha256=advancement.anchor_payload_sha256,
        anchor_payload_size_bytes=advancement.anchor_payload_size_bytes,
        predecessor_sequence=advancement.predecessor_sequence,
        predecessor_lineage_sha256=advancement.predecessor_lineage_sha256,
        lock_path=str(lock),
        ownership_token_sha256=_sha256(token),
        exclusive_create_used=True,
        ownership_token_fsynced=True,
        p68_executed_under_lock=True,
        lock_identity_rechecked=True,
        ownership_bound_release_verified=True,
        advancement_verified=True,
        p68_evidence_state=advancement.evidence_state,
    )
