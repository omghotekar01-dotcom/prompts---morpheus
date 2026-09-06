"""Bind verified P120 canonical replay to verified P122 retained-P121 replay.

P123 composes two independently verified read-only evidence paths and fails closed
unless they identify the same recovery history through the canonical P119 receipt.
The deterministic composition also commits to the selected retained P121 record
identity and dependency evidence-state contracts.

This is consistency evidence only. Mutually consistent inputs may still be stale,
rolled back, or untrusted; P123 grants no startup or mutation authority.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import make_dataclass

from .recovery_p118 import EVIDENCE_STATE as P118_EVIDENCE_STATE
from .recovery_p120 import EVIDENCE_STATE as P120_EVIDENCE_STATE, RecoveryP119ReplayEvidence
from .recovery_p121 import _FIELDS as P121_FIELDS
from .recovery_p122 import EVIDENCE_STATE as P122_EVIDENCE_STATE, RecoveryP121ReplayEvidence

EVIDENCE_STATE = P122_EVIDENCE_STATE + "_P120_REPLAY_COMPOSITION_BINDING_VERIFIED"
TRUTH_BOUNDARY = (
    "This read-only composition gate proves only that compatible supplied P120 and P122 evidence objects agreed during this call on "
    "one recovery sequence, lineage and inherited receipt/identity bindings through the canonical P119 receipt, and that a deterministic "
    "binding over those shared identities, the selected retained P121 record SHA-256 and byte length, and the P118/P120/P122 evidence-state "
    "contracts was computed. It does not authenticate either evidence object or filesystem history, rerun P120/P122 or dependencies, "
    "establish freshness/latest/global/monotonic head truth, prevent coordinated rollback/replay of mutually consistent inputs, retain "
    "a trusted head, authorize startup or mutation, provide CAS, leases, fencing, TPM/HSM protection, remote witnessing, distributed "
    "consensus, HA, native-object recovery, cross-process hot swap, production readiness, benchmark evidence, novelty evidence, or "
    "automatic-control authority."
)

_FIELDS = P121_FIELDS
_P120_FLAGS = (
    "expected_payload_identity_verified",
    "canonical_receipt_verified",
    "dependency_state_verified",
    "p115_p117_composition_binding_recomputed_verified",
)
_P122_FLAGS = (
    "p121_evidence_state_verified",
    "p121_verification_flags_verified",
    "exact_payload_identity_verified",
    "canonical_record_verified",
    "semantic_agreement_verified",
)


def _positive_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _sha256(value: object, *, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or value.lower() != value or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{field} must be 64 lowercase hexadecimal characters")
    return value


def _canonical_sha(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RecoveryP120P122CompositionEvidence = make_dataclass(
    "RecoveryP120P122CompositionEvidence",
    [
        *((field, int if kind == "int" else str) for field, kind in _FIELDS),
        ("retained_p121_record_payload_sha256", str),
        ("retained_p121_record_payload_size_bytes", int),
        ("p120_p122_composition_binding_sha256", str),
        ("p120_contract_verified", bool),
        ("p122_contract_verified", bool),
        ("cross_evidence_identity_verified", bool),
        ("evidence_state", str, EVIDENCE_STATE),
        ("automatic_control_allowed", bool, False),
    ],
    frozen=True,
    namespace={"as_dict": lambda self: {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}},
)


def bind_p120_replay_to_p122_retained_identity(
    receipt: RecoveryP119ReplayEvidence,
    retained: RecoveryP121ReplayEvidence,
) -> RecoveryP120P122CompositionEvidence:
    """Bind compatible P120 and P122 evidence without granting authority."""
    if not isinstance(receipt, RecoveryP119ReplayEvidence):
        raise ValueError("P120 canonical P119 replay evidence has an incompatible type")
    if not isinstance(retained, RecoveryP121ReplayEvidence):
        raise ValueError("P122 retained P121 replay evidence has an incompatible type")

    if receipt.evidence_state != P120_EVIDENCE_STATE:
        raise ValueError("P120 evidence state is incompatible")
    if receipt.p118_evidence_state != P118_EVIDENCE_STATE:
        raise ValueError("P120 embedded P118 evidence state is incompatible")
    if receipt.automatic_control_allowed is not False:
        raise ValueError("P120 evidence must not grant automatic-control authority")
    if any(getattr(receipt, flag, None) is not True for flag in _P120_FLAGS):
        raise ValueError("P120 verification contract is incomplete")

    if retained.evidence_state != P122_EVIDENCE_STATE:
        raise ValueError("P122 evidence state is incompatible")
    if retained.automatic_control_allowed is not False:
        raise ValueError("P122 evidence must not grant automatic-control authority")
    if any(getattr(retained, flag, None) is not True for flag in _P122_FLAGS):
        raise ValueError("P122 verification contract is incomplete")

    values: dict[str, object] = {}
    for field, kind in _FIELDS:
        parser = _positive_int if kind == "int" else _sha256
        left = parser(getattr(receipt, field, None), field=f"P120 {field}")
        right = parser(getattr(retained, field, None), field=f"P122 {field}")
        if left != right:
            raise ValueError(f"P120/P122 evidence disagrees on {field}")
        values[field] = left

    retained_sha = _sha256(retained.stored_payload_sha256, field="P122 retained P121 record SHA-256")
    retained_size = _positive_int(retained.stored_payload_size_bytes, field="P122 retained P121 record size")
    binding = _canonical_sha({
        **values,
        "retained_p121_record_payload_sha256": retained_sha,
        "retained_p121_record_payload_size_bytes": retained_size,
        "p118_evidence_state": P118_EVIDENCE_STATE,
        "p120_evidence_state": P120_EVIDENCE_STATE,
        "p122_evidence_state": P122_EVIDENCE_STATE,
    })

    return RecoveryP120P122CompositionEvidence(
        **values,
        retained_p121_record_payload_sha256=retained_sha,
        retained_p121_record_payload_size_bytes=retained_size,
        p120_p122_composition_binding_sha256=binding,
        p120_contract_verified=True,
        p122_contract_verified=True,
        cross_evidence_identity_verified=True,
    )
