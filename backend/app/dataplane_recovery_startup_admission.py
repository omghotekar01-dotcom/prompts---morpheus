"""Bind verified recovery identity to repeated post-release anchor observation.

P73 closes one narrow startup-evidence composition seam. P67 proves the current
recovery as the exact one-step successor of the predecessor stored before
advancement. P72 proves that, after cooperative advancement/release, a second
local observation still found one canonical anchor identity. P73 requires those
two independently supplied evidence objects to identify the same current
sequence and lineage before emitting a deterministic, read-only startup
admission receipt.

This is an evidence-binding gate, not permission to start or mutate a data
plane. It does not rerun P67/P72, authenticate their inputs, make the local
anchor monotonic, or turn repeated observations into an atomic snapshot.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .dataplane_recovery_anchor_rebootstrap import (
    EVIDENCE_STATE as P67_EVIDENCE_STATE,
    RecoveryStoredExpectedHeadEvidence,
)
from .dataplane_recovery_anchor_repeat_observation import (
    EVIDENCE_STATE as P72_EVIDENCE_STATE,
    RecoveryExpectedHeadRepeatObservationEvidence,
)

EVIDENCE_STATE = "LOCAL_DATA_PLANE_RECOVERY_STARTUP_ADMISSION_CONSISTENCY_VERIFIED"
TRUTH_BOUNDARY = (
    "This gate proves only that compatible supplied P67 and P72 evidence identify the same current recovery sequence/lineage, "
    "and deterministically binds that identity to P67's recovery binding plus P72's repeatedly observed local anchor bytes. "
    "It does not rerun either dependency, authenticate or independently retain evidence, establish latest/global/monotonic "
    "head truth, prevent coordinated rollback, make repeated observations atomic, authorize startup, or provide CAS, leases, "
    "fencing, snapshot isolation, TPM/HSM protection, remote witnessing, distributed consensus, HA, native-object recovery, "
    "cross-process hot swap, production readiness, benchmark evidence, novelty evidence, or automatic-control authority."
)


def _canonical_sha(payload: object) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _positive_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _sha256(value: object, *, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{field} must be 64 lowercase hexadecimal characters")
    if value.lower() != value or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{field} must be 64 lowercase hexadecimal characters")
    return value


@dataclass(frozen=True)
class RecoveryStartupAdmissionEvidence:
    sequence: int
    lineage_sha256: str
    p67_binding_sha256: str
    observed_anchor_payload_sha256: str
    observed_anchor_payload_size_bytes: int
    admission_binding_sha256: str
    recovery_identity_match_verified: bool
    repeated_anchor_identity_bound: bool
    p67_evidence_state: str
    p72_evidence_state: str
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def verify_recovery_startup_admission(
    recovery_evidence: RecoveryStoredExpectedHeadEvidence,
    repeat_observation_evidence: RecoveryExpectedHeadRepeatObservationEvidence,
) -> RecoveryStartupAdmissionEvidence:
    """Bind exact P67 current-recovery identity to exact P72 observed-head identity."""
    if recovery_evidence.evidence_state != P67_EVIDENCE_STATE:
        raise ValueError("P67 recovery evidence has an incompatible evidence state")
    if not (
        recovery_evidence.stored_anchor_identity_verified
        and recovery_evidence.predecessor_anchor_match_verified
        and recovery_evidence.exact_p65_recomputation_verified
        and recovery_evidence.stored_head_recovery_consistency_verified
    ):
        raise ValueError("P67 recovery evidence is not fully consistency verified")
    if recovery_evidence.automatic_control_allowed:
        raise ValueError("P67 recovery evidence cannot authorize automatic control")

    if repeat_observation_evidence.evidence_state != P72_EVIDENCE_STATE:
        raise ValueError("P72 repeat-observation evidence has an incompatible evidence state")
    if not (
        repeat_observation_evidence.lock_absent_before_second_read
        and repeat_observation_evidence.lock_absent_after_second_read
        and repeat_observation_evidence.exact_second_read_identity_verified
        and repeat_observation_evidence.canonical_semantics_reverified
    ):
        raise ValueError("P72 repeat-observation evidence is not fully verified")
    if repeat_observation_evidence.automatic_control_allowed:
        raise ValueError("P72 repeat-observation evidence cannot authorize automatic control")

    p67_sequence = _positive_int(recovery_evidence.sequence, field="P67 recovery sequence")
    p72_sequence = _positive_int(
        repeat_observation_evidence.sequence, field="P72 observed sequence"
    )
    p67_lineage = _sha256(
        recovery_evidence.lineage_sha256, field="P67 recovery lineage SHA-256"
    )
    p72_lineage = _sha256(
        repeat_observation_evidence.lineage_sha256,
        field="P72 observed lineage SHA-256",
    )
    p67_binding = _sha256(
        recovery_evidence.binding_sha256, field="P67 recovery binding SHA-256"
    )
    observed_payload_sha = _sha256(
        repeat_observation_evidence.anchor_payload_sha256,
        field="P72 observed anchor payload SHA-256",
    )
    observed_payload_size = _positive_int(
        repeat_observation_evidence.anchor_payload_size_bytes,
        field="P72 observed anchor payload size",
    )

    if p67_sequence != p72_sequence or p67_lineage != p72_lineage:
        raise ValueError("P67 current recovery identity does not match P72 observed anchor head")

    binding_payload = {
        "sequence": p67_sequence,
        "lineage_sha256": p67_lineage,
        "p67_binding_sha256": p67_binding,
        "observed_anchor_payload_sha256": observed_payload_sha,
        "observed_anchor_payload_size_bytes": observed_payload_size,
        "p67_evidence_state": recovery_evidence.evidence_state,
        "p72_evidence_state": repeat_observation_evidence.evidence_state,
    }
    return RecoveryStartupAdmissionEvidence(
        sequence=p67_sequence,
        lineage_sha256=p67_lineage,
        p67_binding_sha256=p67_binding,
        observed_anchor_payload_sha256=observed_payload_sha,
        observed_anchor_payload_size_bytes=observed_payload_size,
        admission_binding_sha256=_canonical_sha(binding_payload),
        recovery_identity_match_verified=True,
        repeated_anchor_identity_bound=True,
        p67_evidence_state=recovery_evidence.evidence_state,
        p72_evidence_state=repeat_observation_evidence.evidence_state,
    )
