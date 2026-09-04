"""Re-observe one P71 recovery anchor and bind a second local snapshot to it.

P72 tightens one narrow evidence seam left explicit by P71. P71 proves one
post-release observation of the expected-head anchor after the P70 cooperative
lock has been released. P72 performs a separate second observation: the same
lock path must be absent before and after the read, the exact bytes must still
match P71's size and SHA-256 identity, and the canonical sequence/lineage
semantics must still match.

This is repeated observation, not atomicity. A writer can act between any two
filesystem operations, and a transient change that is fully reverted between
checks may be invisible. P72 therefore provides evidence that two local
snapshots agreed; it is not a lease, fencing protocol, compare-and-swap,
snapshot-isolation mechanism, or trusted latest-head service.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from .dataplane_recovery_anchor_observation import (
    EVIDENCE_STATE as P71_EVIDENCE_STATE,
    RecoveryExpectedHeadPostReleaseObservationEvidence,
)
from .dataplane_recovery_anchor_ownership import EVIDENCE_STATE as P70_EVIDENCE_STATE
from .dataplane_recovery_anchor_store import load_recovery_expected_head

EVIDENCE_STATE = "LOCAL_DATA_PLANE_RECOVERY_EXPECTED_HEAD_REPEAT_OBSERVATION_VERIFIED"
TRUTH_BOUNDARY = (
    "This gate proves only that a second local post-P71 observation found the recorded cooperative lock absent before and "
    "after its anchor read, and that the exact bytes and canonical sequence/lineage semantics still matched P71 evidence. "
    "The checks are separate filesystem operations, not an atomic transaction: a writer can race between checks, and a "
    "transient mutation that is fully reverted between observations may be invisible. P72 is therefore not CAS, a lease, "
    "fencing, snapshot isolation, global/latest-head truth, rollback resistance, TPM/HSM protection, remote witnessing, "
    "distributed consensus, HA, native-object recovery, cross-process hot swap, production readiness, benchmark evidence, "
    "or automatic-control authority."
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class RecoveryExpectedHeadRepeatObservationEvidence:
    sequence: int
    lineage_sha256: str
    anchor_payload_sha256: str
    anchor_payload_size_bytes: int
    lock_path: str
    lock_absent_before_second_read: bool
    lock_absent_after_second_read: bool
    exact_second_read_identity_verified: bool
    canonical_semantics_reverified: bool
    p71_evidence_state: str
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def verify_recovery_expected_head_repeat_observation(
    path: str | os.PathLike[str],
    observation_evidence: RecoveryExpectedHeadPostReleaseObservationEvidence,
) -> RecoveryExpectedHeadRepeatObservationEvidence:
    """Bind a second unlocked local anchor observation to exact P71 evidence."""
    target = Path(path)
    if not target.name:
        raise ValueError("recovery expected-head store path must name a file")

    if observation_evidence.evidence_state != P71_EVIDENCE_STATE:
        raise ValueError("P71 observation evidence has an incompatible evidence state")
    if observation_evidence.p70_evidence_state != P70_EVIDENCE_STATE:
        raise ValueError("P71 observation evidence is not bound to the expected P70 evidence state")
    if not observation_evidence.lock_absent_when_observed:
        raise ValueError("P71 observation evidence does not prove lock absence")
    if not observation_evidence.exact_byte_identity_verified:
        raise ValueError("P71 observation evidence does not prove exact byte identity")
    if not observation_evidence.canonical_semantics_verified:
        raise ValueError("P71 observation evidence does not prove canonical semantics")
    if observation_evidence.automatic_control_allowed:
        raise ValueError("P71 observation evidence cannot authorize automatic control")

    lock = Path(observation_evidence.lock_path)
    if lock.exists():
        raise RuntimeError("P72 observed the cooperative lock present before the second anchor read")

    try:
        payload = target.read_bytes()
    except FileNotFoundError as exc:
        raise RuntimeError("P72 expected-head anchor disappeared before the second observation") from exc

    if lock.exists():
        raise RuntimeError("P72 observed the cooperative lock present after the second anchor read")
    if len(payload) != observation_evidence.anchor_payload_size_bytes:
        raise ValueError("second-observation anchor byte length does not match P71 evidence")

    payload_sha256 = _sha256(payload)
    if payload_sha256 != observation_evidence.anchor_payload_sha256:
        raise ValueError("second-observation anchor SHA-256 does not match P71 evidence")

    stored = load_recovery_expected_head(
        target,
        expected_payload_sha256=observation_evidence.anchor_payload_sha256,
    )
    if stored.sequence != observation_evidence.sequence:
        raise ValueError("second-observation anchor sequence does not match P71 evidence")
    if stored.lineage_sha256 != observation_evidence.lineage_sha256:
        raise ValueError("second-observation anchor lineage does not match P71 evidence")

    # Recheck after canonical parsing as well. This still does not make the
    # preceding read/parse sequence atomic; it only narrows what this call can
    # truthfully claim about cooperative activity observed at its boundaries.
    if lock.exists():
        raise RuntimeError("P72 observed the cooperative lock present after canonical revalidation")

    return RecoveryExpectedHeadRepeatObservationEvidence(
        sequence=stored.sequence,
        lineage_sha256=stored.lineage_sha256,
        anchor_payload_sha256=payload_sha256,
        anchor_payload_size_bytes=len(payload),
        lock_path=str(lock),
        lock_absent_before_second_read=True,
        lock_absent_after_second_read=True,
        exact_second_read_identity_verified=True,
        canonical_semantics_reverified=True,
        p71_evidence_state=observation_evidence.evidence_state,
    )
