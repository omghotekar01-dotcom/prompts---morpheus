"""Bind verified P115 canonical replay to verified P117 retained-P116 replay.

P118 composes two independently verified read-only evidence paths and fails closed
unless they identify the same recovery history through the canonical P114 receipt.
The deterministic composition also commits to the selected retained P116 record
identity and dependency evidence-state contracts.

This is consistency evidence only. Mutually consistent inputs may still be stale,
rolled back, or untrusted; P118 grants no startup or mutation authority.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .recovery_p113 import EVIDENCE_STATE as P113_EVIDENCE_STATE
from .recovery_p115 import EVIDENCE_STATE as P115_EVIDENCE_STATE, RecoveryP114ReplayEvidence
from .recovery_p116 import _FIELDS as P116_FIELDS
from .recovery_p117 import EVIDENCE_STATE as P117_EVIDENCE_STATE, RecoveryP116ReplayEvidence

EVIDENCE_STATE = P117_EVIDENCE_STATE + "_P115_REPLAY_COMPOSITION_BINDING_VERIFIED"
TRUTH_BOUNDARY = (
    "This read-only composition gate proves only that compatible supplied P115 and P117 evidence objects agreed during this call on "
    "one recovery sequence, lineage and inherited receipt/identity bindings through the canonical P114 receipt, and that a deterministic "
    "binding over those shared identities, the selected retained P116 record SHA-256 and byte length, and the P113/P115/P117 evidence-state "
    "contracts was computed. It does not authenticate either evidence object or filesystem history, rerun P115/P117 or dependencies, "
    "establish freshness/latest/global/monotonic head truth, prevent coordinated rollback/replay of mutually consistent inputs, retain "
    "a trusted head, authorize startup or mutation, provide CAS, leases, fencing, TPM/HSM protection, remote witnessing, distributed "
    "consensus, HA, native-object recovery, cross-process hot swap, production readiness, benchmark evidence, novelty evidence, or "
    "automatic-control authority."
)

_FIELDS = P116_FIELDS
_P115_FLAGS = (
    "expected_payload_identity_verified",
    "canonical_receipt_verified",
    "dependency_state_verified",
    "p110_p112_composition_binding_recomputed_verified",
)
_P117_FLAGS = (
    "p116_evidence_state_verified",
    "p116_verification_flags_verified",
    "exact_payload_identity_verified",
    "canonical_record_verified",
    "semantic_agreement_verified",
)


def _positive_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _sha256(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value.lower() != value
        or any(ch not in "0123456789abcdef" for ch in value)
    ):
        raise ValueError(f"{field} must be 64 lowercase hexadecimal characters")
    return value


def _canonical_sha(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class RecoveryP115P117CompositionEvidence:
    sequence: int
    lineage_sha256: str
    binding_receipt_payload_sha256: str
    binding_receipt_payload_size_bytes: int
    receipt_identity_binding_sha256: str
    retained_identity_payload_sha256: str
    retained_identity_payload_size_bytes: int
    replay_stored_identity_binding_sha256: str
    replay_binding_receipt_payload_sha256: str
    replay_binding_receipt_payload_size_bytes: int
    retained_replay_identity_payload_sha256: str
    retained_replay_identity_payload_size_bytes: int
    replay_retained_identity_binding_sha256: str
    replay_retained_identity_binding_receipt_payload_sha256: str
    replay_retained_identity_binding_receipt_payload_size_bytes: int
    retained_replay_receipt_identity_payload_sha256: str
    retained_replay_receipt_identity_payload_size_bytes: int
    replay_retained_receipt_identity_binding_sha256: str
    replay_retained_receipt_identity_binding_receipt_payload_sha256: str
    replay_retained_receipt_identity_binding_receipt_payload_size_bytes: int
    retained_replayed_receipt_identity_payload_sha256: str
    retained_replayed_receipt_identity_payload_size_bytes: int
    replayed_receipt_retained_identity_binding_sha256: str
    replayed_receipt_retained_identity_binding_receipt_payload_sha256: str
    replayed_receipt_retained_identity_binding_receipt_payload_size_bytes: int
    retained_p101_record_payload_sha256: str
    retained_p101_record_payload_size_bytes: int
    p100_p102_composition_binding_sha256: str
    p104_receipt_payload_sha256: str
    p104_receipt_payload_size_bytes: int
    retained_p106_record_payload_sha256: str
    retained_p106_record_payload_size_bytes: int
    p105_p107_composition_binding_sha256: str
    p109_receipt_payload_sha256: str
    p109_receipt_payload_size_bytes: int
    retained_p111_record_payload_sha256: str
    retained_p111_record_payload_size_bytes: int
    p110_p112_composition_binding_sha256: str
    p114_receipt_payload_sha256: str
    p114_receipt_payload_size_bytes: int
    retained_p116_record_payload_sha256: str
    retained_p116_record_payload_size_bytes: int
    p115_p117_composition_binding_sha256: str
    p115_contract_verified: bool
    p117_contract_verified: bool
    cross_evidence_identity_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def bind_p115_replay_to_p117_retained_identity(
    receipt: RecoveryP114ReplayEvidence,
    retained: RecoveryP116ReplayEvidence,
) -> RecoveryP115P117CompositionEvidence:
    """Bind compatible P115 and P117 evidence without granting authority."""
    if not isinstance(receipt, RecoveryP114ReplayEvidence):
        raise ValueError("P115 canonical P114 replay evidence has an incompatible type")
    if not isinstance(retained, RecoveryP116ReplayEvidence):
        raise ValueError("P117 retained P116 replay evidence has an incompatible type")

    if receipt.evidence_state != P115_EVIDENCE_STATE:
        raise ValueError("P115 evidence state is incompatible")
    if receipt.p113_evidence_state != P113_EVIDENCE_STATE:
        raise ValueError("P115 embedded P113 evidence state is incompatible")
    if receipt.automatic_control_allowed is not False:
        raise ValueError("P115 evidence must not grant automatic-control authority")
    if any(getattr(receipt, flag, None) is not True for flag in _P115_FLAGS):
        raise ValueError("P115 verification contract is incomplete")

    if retained.evidence_state != P117_EVIDENCE_STATE:
        raise ValueError("P117 evidence state is incompatible")
    if retained.automatic_control_allowed is not False:
        raise ValueError("P117 evidence must not grant automatic-control authority")
    if any(getattr(retained, flag, None) is not True for flag in _P117_FLAGS):
        raise ValueError("P117 verification contract is incomplete")

    values: dict[str, object] = {}
    for field, kind in _FIELDS:
        left_raw = getattr(receipt, field, None)
        right_raw = getattr(retained, field, None)
        parser = _positive_int if kind == "int" else _sha256
        left = parser(left_raw, field=f"P115 {field}")
        right = parser(right_raw, field=f"P117 {field}")
        if left != right:
            raise ValueError(f"P115/P117 evidence disagrees on {field}")
        values[field] = left

    retained_sha = _sha256(retained.stored_payload_sha256, field="P117 retained P116 record SHA-256")
    retained_size = _positive_int(retained.stored_payload_size_bytes, field="P117 retained P116 record size")

    binding = _canonical_sha(
        {
            **values,
            "retained_p116_record_payload_sha256": retained_sha,
            "retained_p116_record_payload_size_bytes": retained_size,
            "p113_evidence_state": P113_EVIDENCE_STATE,
            "p115_evidence_state": P115_EVIDENCE_STATE,
            "p117_evidence_state": P117_EVIDENCE_STATE,
        }
    )

    return RecoveryP115P117CompositionEvidence(
        **values,
        retained_p116_record_payload_sha256=retained_sha,
        retained_p116_record_payload_size_bytes=retained_size,
        p115_p117_composition_binding_sha256=binding,
        p115_contract_verified=True,
        p117_contract_verified=True,
        cross_evidence_identity_verified=True,
    )
