"""Bind verified P125 canonical replay to verified P127 retained-P126 replay.

P128 composes two independently verified read-only evidence paths and fails closed
unless they identify the same recovery history through the canonical P124 receipt.
The deterministic composition also commits to the selected retained P126 record
identity and dependency evidence-state contracts.

This is consistency evidence only. Mutually consistent inputs may still be stale,
rolled back, or untrusted; P128 grants no startup or mutation authority.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import make_dataclass

from .recovery_p123 import EVIDENCE_STATE as P123_EVIDENCE_STATE
from .recovery_p125 import EVIDENCE_STATE as P125_EVIDENCE_STATE, RecoveryP124ReplayEvidence
from .recovery_p126 import _FIELDS as P126_FIELDS
from .recovery_p127 import (
    EVIDENCE_STATE as P127_EVIDENCE_STATE,
    RecoveryP125ReplayIdentityVerificationEvidence,
)

EVIDENCE_STATE = P127_EVIDENCE_STATE + "_P125_REPLAY_COMPOSITION_BINDING_VERIFIED"
TRUTH_BOUNDARY = (
    "This read-only composition gate proves only that compatible supplied P125 and P127 evidence objects agreed during this call on "
    "one recovery sequence, lineage and inherited receipt/identity bindings through the canonical P124 receipt, and that a deterministic "
    "binding over those shared identities, the selected retained P126 record SHA-256 and byte length, and the P123/P125/P127 evidence-state "
    "contracts was computed. It does not authenticate either evidence object or filesystem history, rerun P125/P127 or dependencies, "
    "establish freshness/latest/global/monotonic head truth, prevent coordinated rollback/replay of mutually consistent inputs, retain "
    "a trusted head, authorize startup or mutation, provide CAS, leases, fencing, TPM/HSM protection, remote witnessing, distributed "
    "consensus, HA, native-object recovery, cross-process hot swap, production readiness, benchmark evidence, novelty evidence, or "
    "automatic-control authority."
)

_FIELDS = P126_FIELDS
_P125_FLAGS = (
    "expected_payload_identity_verified",
    "canonical_receipt_verified",
    "dependency_state_verified",
    "p120_p122_composition_binding_recomputed_verified",
)
_P127_FLAGS = (
    "exact_size_verified",
    "exact_sha256_verified",
    "strict_schema_verified",
    "canonical_encoding_verified",
    "retained_identity_verified",
    "p125_evidence_state_verified",
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


RecoveryP125P127CompositionEvidence = make_dataclass(
    "RecoveryP125P127CompositionEvidence",
    [
        *((field, int if kind == "int" else str) for field, kind in _FIELDS),
        ("retained_p126_record_payload_sha256", str),
        ("retained_p126_record_payload_size_bytes", int),
        ("p125_p127_composition_binding_sha256", str),
        ("p125_contract_verified", bool),
        ("p127_contract_verified", bool),
        ("cross_evidence_identity_verified", bool),
        ("evidence_state", str, EVIDENCE_STATE),
        ("automatic_control_allowed", bool, False),
    ],
    frozen=True,
    namespace={"as_dict": lambda self: {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}},
)


def bind_p125_replay_to_p127_retained_identity(
    receipt: RecoveryP124ReplayEvidence,
    retained: RecoveryP125ReplayIdentityVerificationEvidence,
) -> RecoveryP125P127CompositionEvidence:
    """Bind compatible P125 and P127 evidence without granting authority."""
    if not isinstance(receipt, RecoveryP124ReplayEvidence):
        raise ValueError("P125 canonical P124 replay evidence has an incompatible type")
    if not isinstance(retained, RecoveryP125ReplayIdentityVerificationEvidence):
        raise ValueError("P127 retained P126 replay evidence has an incompatible type")

    if receipt.evidence_state != P125_EVIDENCE_STATE:
        raise ValueError("P125 evidence state is incompatible")
    if receipt.p123_evidence_state != P123_EVIDENCE_STATE:
        raise ValueError("P125 embedded P123 evidence state is incompatible")
    if receipt.automatic_control_allowed is not False:
        raise ValueError("P125 evidence must not grant automatic-control authority")
    if any(getattr(receipt, flag, None) is not True for flag in _P125_FLAGS):
        raise ValueError("P125 verification contract is incomplete")

    if retained.evidence_state != P127_EVIDENCE_STATE:
        raise ValueError("P127 evidence state is incompatible")
    if retained.automatic_control_allowed is not False:
        raise ValueError("P127 evidence must not grant automatic-control authority")
    if any(getattr(retained, flag, None) is not True for flag in _P127_FLAGS):
        raise ValueError("P127 verification contract is incomplete")

    values: dict[str, object] = {}
    for field, kind in _FIELDS:
        parser = _positive_int if kind == "int" else _sha256
        left = parser(getattr(receipt, field, None), field=f"P125 {field}")
        right = parser(getattr(retained, field, None), field=f"P127 {field}")
        if left != right:
            raise ValueError(f"P125/P127 evidence disagrees on {field}")
        values[field] = left

    retained_sha = _sha256(retained.stored_payload_sha256, field="P127 retained P126 record SHA-256")
    retained_size = _positive_int(retained.stored_payload_size_bytes, field="P127 retained P126 record size")
    binding = _canonical_sha(
        {
            **values,
            "retained_p126_record_payload_sha256": retained_sha,
            "retained_p126_record_payload_size_bytes": retained_size,
            "p123_evidence_state": P123_EVIDENCE_STATE,
            "p125_evidence_state": P125_EVIDENCE_STATE,
            "p127_evidence_state": P127_EVIDENCE_STATE,
        }
    )

    return RecoveryP125P127CompositionEvidence(
        **values,
        retained_p126_record_payload_sha256=retained_sha,
        retained_p126_record_payload_size_bytes=retained_size,
        p125_p127_composition_binding_sha256=binding,
        p125_contract_verified=True,
        p127_contract_verified=True,
        cross_evidence_identity_verified=True,
    )
