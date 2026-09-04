"""Verify the exact expected-head anchor observed after a completed P70 release.

P71 closes one narrow evidence seam left explicit by P70. P70 binds cooperative lock
release to the exact lock instance it created, but its returned evidence is produced
after release without an independent read of the now-unlocked anchor. P71 performs
that independent observation: the P70 lock must be absent, the currently stored anchor
bytes must match P70's exact size and SHA-256 identity, and canonical anchor semantics
must match P70's sequence and lineage identity.

This is an observation gate, not a concurrency primitive. Another writer can change the
anchor immediately after the read or acquire the lock immediately after the absence
check. P71 therefore proves only what was observed during this verification call; it
does not create a lease, fencing token, compare-and-swap, or durable/global latest-head
property.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from .dataplane_recovery_anchor_ownership import (
    EVIDENCE_STATE as P70_EVIDENCE_STATE,
    RecoveryExpectedHeadOwnershipBoundAdvanceEvidence,
)
from .dataplane_recovery_anchor_store import load_recovery_expected_head

EVIDENCE_STATE = "LOCAL_DATA_PLANE_RECOVERY_EXPECTED_HEAD_POST_RELEASE_OBSERVATION_VERIFIED"
TRUTH_BOUNDARY = (
    "This gate proves only that, during one post-P70 observation, the recorded P70 lock path was absent and the exact anchor "
    "bytes then read matched P70's byte length and SHA-256 identity, while canonical parsed sequence/lineage semantics matched "
    "the P70 successor. The observation is not atomic with future filesystem operations: another writer may acquire the lock "
    "or replace the anchor immediately afterward. P71 is therefore not a CAS, lease, fencing token, lock, snapshot-isolation "
    "mechanism, or globally trusted latest-head proof. It does not exclude writers bypassing P70, recover stale locks, provide "
    "rollback resistance, TPM/HSM protection, remote witnessing, distributed consensus, HA, native-object recovery, "
    "cross-process hot swap, production readiness, benchmark performance, or automatic-control authority."
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class RecoveryExpectedHeadPostReleaseObservationEvidence:
    sequence: int
    lineage_sha256: str
    anchor_payload_sha256: str
    anchor_payload_size_bytes: int
    lock_path: str
    lock_absent_when_observed: bool
    exact_byte_identity_verified: bool
    canonical_semantics_verified: bool
    p70_evidence_state: str
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def verify_recovery_expected_head_post_release(
    path: str | os.PathLike[str],
    ownership_evidence: RecoveryExpectedHeadOwnershipBoundAdvanceEvidence,
) -> RecoveryExpectedHeadPostReleaseObservationEvidence:
    """Independently observe and bind the unlocked anchor to exact P70 evidence."""
    target = Path(path)
    if not target.name:
        raise ValueError("recovery expected-head store path must name a file")

    if ownership_evidence.evidence_state != P70_EVIDENCE_STATE:
        raise ValueError("P70 ownership evidence has an incompatible evidence state")
    if not ownership_evidence.exclusive_create_used:
        raise ValueError("P70 ownership evidence does not prove exclusive lock creation")
    if not ownership_evidence.ownership_token_fsynced:
        raise ValueError("P70 ownership evidence does not prove ownership-token fsync")
    if not ownership_evidence.p68_executed_under_lock:
        raise ValueError("P70 ownership evidence does not prove P68 execution under lock")
    if not ownership_evidence.lock_identity_rechecked:
        raise ValueError("P70 ownership evidence does not prove lock identity recheck")
    if not ownership_evidence.ownership_bound_release_verified:
        raise ValueError("P70 ownership evidence does not prove ownership-bound release")
    if not ownership_evidence.advancement_verified:
        raise ValueError("P70 ownership evidence does not prove advancement")
    if ownership_evidence.automatic_control_allowed:
        raise ValueError("P70 ownership evidence cannot authorize automatic control")

    lock = Path(ownership_evidence.lock_path)
    if lock.exists():
        raise RuntimeError("P71 observed the P70 lock path present; post-release anchor is not quiescent for this observation")

    try:
        payload = target.read_bytes()
    except FileNotFoundError as exc:
        raise RuntimeError("P71 expected-head anchor disappeared before post-release observation") from exc

    if len(payload) != ownership_evidence.anchor_payload_size_bytes:
        raise ValueError("post-release anchor byte length does not match P70 evidence")
    payload_sha256 = _sha256(payload)
    if payload_sha256 != ownership_evidence.anchor_payload_sha256:
        raise ValueError("post-release anchor SHA-256 does not match P70 evidence")

    # P66's loader intentionally returns only the canonical semantic head
    # (sequence + lineage). Exact byte size and digest identity are verified
    # from the raw payload above before parsing, so do not infer fields that
    # are deliberately absent from RecoveryStoredHead.
    stored = load_recovery_expected_head(
        target,
        expected_payload_sha256=ownership_evidence.anchor_payload_sha256,
    )
    if stored.sequence != ownership_evidence.sequence:
        raise ValueError("post-release anchor sequence does not match P70 evidence")
    if stored.lineage_sha256 != ownership_evidence.lineage_sha256:
        raise ValueError("post-release anchor lineage does not match P70 evidence")

    return RecoveryExpectedHeadPostReleaseObservationEvidence(
        sequence=stored.sequence,
        lineage_sha256=stored.lineage_sha256,
        anchor_payload_sha256=payload_sha256,
        anchor_payload_size_bytes=len(payload),
        lock_path=str(lock),
        lock_absent_when_observed=True,
        exact_byte_identity_verified=True,
        canonical_semantics_verified=True,
        p70_evidence_state=ownership_evidence.evidence_state,
    )
