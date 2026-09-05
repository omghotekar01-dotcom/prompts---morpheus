"""Bind verified P110 canonical replay to verified P112 retained-P111 replay.

P113 composes two independently verified read-only evidence paths and fails closed
unless they identify the same recovery history through the canonical P109 receipt.
The deterministic composition also commits to the selected retained P111 record
identity and dependency evidence-state contracts.

This is consistency evidence only. Mutually consistent inputs may still be stale,
rolled back, or untrusted; P113 grants no startup or mutation authority.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .recovery_p108 import EVIDENCE_STATE as P108_EVIDENCE_STATE
from .recovery_p110 import EVIDENCE_STATE as P110_EVIDENCE_STATE, RecoveryP109ReplayEvidence
from .recovery_p111 import _FIELDS as P111_FIELDS
from .recovery_p112 import EVIDENCE_STATE as P112_EVIDENCE_STATE, RecoveryP111ReplayEvidence

EVIDENCE_STATE = P112_EVIDENCE_STATE + "_P110_REPLAY_COMPOSITION_BINDING_VERIFIED"
TRUTH_BOUNDARY = (
    "This read-only composition gate proves only that compatible supplied P110 and P112 evidence objects agreed during this call on "
    "one recovery sequence, lineage and inherited receipt/identity bindings through the canonical P109 receipt, and that a deterministic "
    "binding over those shared identities, the selected retained P111 record SHA-256 and byte length, and the P108/P110/P112 evidence-state "
    "contracts was computed. It does not authenticate either evidence object or filesystem history, rerun P110/P112 or dependencies, "
    "establish freshness/latest/global/monotonic head truth, prevent coordinated rollback/replay of mutually consistent inputs, retain "
    "a trusted head, authorize startup or mutation, provide CAS, leases, fencing, TPM/HSM protection, remote witnessing, distributed "
    "consensus, HA, native-object recovery, cross-process hot swap, production readiness, benchmark evidence, novelty evidence, or "
    "automatic-control authority."
)

_FIELDS = P111_FIELDS
_P110_FLAGS = (
    "expected_payload_identity_verified",
    "canonical_receipt_verified",
    "dependency_state_verified",
    "p105_p107_composition_binding_recomputed_verified",
)
_P112_FLAGS = (
    "p111_evidence_state_verified",
    "p111_verification_flags_verified",
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
class RecoveryP110P112CompositionEvidence:
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
    p110_contract_verified: bool
    p112_contract_verified: bool
    cross_evidence_identity_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def bind_p110_replay_to_p112_retained_identity(
    receipt: RecoveryP109ReplayEvidence,
    retained: RecoveryP111ReplayEvidence,
) -> RecoveryP110P112CompositionEvidence:
    """Bind compatible P110 and P112 evidence without granting authority."""
    if not isinstance(receipt, RecoveryP109ReplayEvidence):
        raise ValueError("P110 canonical P109 replay evidence has an incompatible type")
    if not isinstance(retained, RecoveryP111ReplayEvidence):
        raise ValueError("P112 retained P111 replay evidence has an incompatible type")

    if receipt.evidence_state != P110_EVIDENCE_STATE:
        raise ValueError("P110 evidence state is incompatible")
    if receipt.p108_evidence_state != P108_EVIDENCE_STATE:
        raise ValueError("P110 embedded P108 evidence state is incompatible")
    if receipt.automatic_control_allowed is not False:
        raise ValueError("P110 evidence must not grant automatic-control authority")
    if any(getattr(receipt, flag, None) is not True for flag in _P110_FLAGS):
        raise ValueError("P110 verification contract is incomplete")

    if retained.evidence_state != P112_EVIDENCE_STATE:
        raise ValueError("P112 evidence state is incompatible")
    if retained.automatic_control_allowed is not False:
        raise ValueError("P112 evidence must not grant automatic-control authority")
    if any(getattr(retained, flag, None) is not True for flag in _P112_FLAGS):
        raise ValueError("P112 verification contract is incomplete")

    values: dict[str, object] = {}
    for field, kind in _FIELDS:
        left_raw = getattr(receipt, field, None)
        right_raw = getattr(retained, field, None)
        parser = _positive_int if kind == "int" else _sha256
        left = parser(left_raw, field=f"P110 {field}")
        right = parser(right_raw, field=f"P112 {field}")
        if left != right:
            raise ValueError(f"P110/P112 evidence disagrees on {field}")
        values[field] = left

    retained_sha = _sha256(retained.stored_payload_sha256, field="P112 retained P111 record SHA-256")
    retained_size = _positive_int(retained.stored_payload_size_bytes, field="P112 retained P111 record size")

    binding = _canonical_sha(
        {
            **values,
            "retained_p111_record_payload_sha256": retained_sha,
            "retained_p111_record_payload_size_bytes": retained_size,
            "p108_evidence_state": P108_EVIDENCE_STATE,
            "p110_evidence_state": P110_EVIDENCE_STATE,
            "p112_evidence_state": P112_EVIDENCE_STATE,
        }
    )

    return RecoveryP110P112CompositionEvidence(
        **values,
        retained_p111_record_payload_sha256=retained_sha,
        retained_p111_record_payload_size_bytes=retained_size,
        p110_p112_composition_binding_sha256=binding,
        p110_contract_verified=True,
        p112_contract_verified=True,
        cross_evidence_identity_verified=True,
    )
