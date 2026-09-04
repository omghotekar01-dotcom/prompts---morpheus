"""Serialize cooperating P68 local expected-head advancements with an exclusive lock file.

P69 closes one narrow local concurrency seam left explicit by P68. A caller that routes
all local expected-head advancement attempts through this gate must first acquire one
same-directory lock file using O_CREAT|O_EXCL. Only after acquisition does P69 invoke
P68, so P68's exact predecessor recheck and successor publication occur while that
cooperative lock is held. The lock is removed on both success and downstream failure.

This is deliberately a cooperative local-filesystem protocol, not a universal CAS or
distributed lock. Writers that bypass P69 are not excluded. A process crash can leave
a stale lock file, which this gate intentionally refuses to steal automatically. The
atomicity/durability semantics of exclusive creation and replacement remain those of
the selected OS/filesystem; no claim is made for every network/distributed filesystem.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .dataplane_recovery_anchor_advance import (
    EVIDENCE_STATE as P68_EVIDENCE_STATE,
    RecoveryExpectedHeadAdvanceEvidence,
    advance_recovery_expected_head,
)
from .dataplane_recovery_anchor_rebootstrap import RecoveryStoredExpectedHeadEvidence
from .dataplane_recovery_anchor_store import RecoveryExpectedHeadStoreEvidence

EVIDENCE_STATE = "LOCAL_DATA_PLANE_RECOVERY_EXPECTED_HEAD_COOPERATIVE_SERIALIZATION_VERIFIED"
TRUTH_BOUNDARY = (
    "This gate proves only that one P68 advancement executed while this process held a caller-selected same-directory "
    "cooperative lock file acquired with O_CREAT|O_EXCL, and that the lock was released before successful evidence was "
    "returned. Cooperating writers using the same lock path are fail-closed while it exists. It is not a universal or "
    "kernel-enforced compare-and-swap on the anchor: writers that bypass P69 are not excluded, a crashed process can leave "
    "a stale lock that this gate will not steal automatically, and exclusive-create/replace semantics depend on the selected "
    "OS and filesystem (especially network/distributed filesystems). It does not establish lock ownership authentication, "
    "leases, fencing tokens, starvation freedom, global latest-head knowledge, rollback resistance, TPM/HSM protection, "
    "remote witnessing, distributed consensus, HA, native-object recovery, cross-process hot swap, production readiness, "
    "benchmark performance, or automatic-control authority."
)


@dataclass(frozen=True)
class RecoveryExpectedHeadSerializedAdvanceEvidence:
    sequence: int
    lineage_sha256: str
    anchor_payload_sha256: str
    anchor_payload_size_bytes: int
    predecessor_sequence: int
    predecessor_lineage_sha256: str
    lock_path: str
    exclusive_create_used: bool
    cooperative_lock_acquired: bool
    p68_executed_under_lock: bool
    cooperative_lock_released: bool
    serialized_advancement_verified: bool
    p68_evidence_state: str
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def _default_lock_path(target: Path) -> Path:
    return target.with_name(f".{target.name}.morpheus-head-advance.lock")


def advance_recovery_expected_head_serialized(
    path: str | os.PathLike[str],
    predecessor_store_evidence: RecoveryExpectedHeadStoreEvidence,
    recovery_evidence: RecoveryStoredExpectedHeadEvidence,
    *,
    lock_path: str | os.PathLike[str] | None = None,
) -> RecoveryExpectedHeadSerializedAdvanceEvidence:
    """Run one P68 advancement under a fail-closed cooperative exclusive-create lock."""
    target = Path(path)
    if not target.name:
        raise ValueError("recovery expected-head store path must name a file")

    lock = Path(lock_path) if lock_path is not None else _default_lock_path(target)
    if not lock.name:
        raise ValueError("recovery expected-head lock path must name a file")
    if lock.parent.resolve() != target.parent.resolve():
        raise ValueError("P69 lock path must be in the same directory as the expected-head anchor")
    if lock == target:
        raise ValueError("P69 lock path must differ from the expected-head anchor path")

    lock.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        descriptor = os.open(lock, flags, 0o600)
    except FileExistsError as exc:
        raise RuntimeError("P69 cooperative advancement lock already exists; refusing unsafe lock stealing") from exc

    advancement: RecoveryExpectedHeadAdvanceEvidence | None = None
    try:
        with os.fdopen(descriptor, "wb") as handle:
            # Diagnostic only. Correctness relies on exclusive creation, not this content.
            handle.write(f"pid={os.getpid()}\n".encode("ascii"))
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
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            # Missing lock means the cooperative protocol was externally disturbed.
            # On the success path this is detected below before evidence is returned.
            pass

    if advancement is None:
        raise RuntimeError("P69 advancement completed without P68 evidence")
    if lock.exists():
        raise RuntimeError("P69 cooperative advancement lock was not released")

    return RecoveryExpectedHeadSerializedAdvanceEvidence(
        sequence=advancement.sequence,
        lineage_sha256=advancement.lineage_sha256,
        anchor_payload_sha256=advancement.anchor_payload_sha256,
        anchor_payload_size_bytes=advancement.anchor_payload_size_bytes,
        predecessor_sequence=advancement.predecessor_sequence,
        predecessor_lineage_sha256=advancement.predecessor_lineage_sha256,
        lock_path=str(lock),
        exclusive_create_used=True,
        cooperative_lock_acquired=True,
        p68_executed_under_lock=True,
        cooperative_lock_released=True,
        serialized_advancement_verified=True,
        p68_evidence_state=advancement.evidence_state,
    )
