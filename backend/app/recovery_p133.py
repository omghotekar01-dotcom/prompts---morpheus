"""Bind verified P130 receipt replay to verified P132 retained-P131 replay.

P133 composes two independently verified read-only evidence paths and fails closed
unless they identify the same canonical P129 receipt through P131's retained identity.
The deterministic composition also commits to the selected retained P131 record
identity and the dependency evidence-state contracts.

This is consistency evidence only. Mutually consistent inputs may still be stale,
rolled back, or untrusted; P133 grants no startup or mutation authority.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import make_dataclass

from .recovery_p128 import EVIDENCE_STATE as P128_EVIDENCE_STATE
from .recovery_p130 import EVIDENCE_STATE as P130_EVIDENCE_STATE, RecoveryP129ReceiptVerificationEvidence
from .recovery_p131 import _FIELDS as P131_FIELDS
from .recovery_p132 import (
    EVIDENCE_STATE as P132_EVIDENCE_STATE,
    RecoveryP130ReceiptIdentityVerificationEvidence,
)

EVIDENCE_STATE = P132_EVIDENCE_STATE + "_P130_REPLAY_COMPOSITION_BINDING_VERIFIED"
TRUTH_BOUNDARY = (
    "This read-only composition gate proves only that compatible supplied P130 and P132 evidence objects agreed during this call on one "
    "canonical P129 receipt identity, and that a deterministic binding over that shared identity, the selected retained P131 record SHA-256 "
    "and byte length, and the P128/P130/P132 evidence-state contracts was computed. It does not authenticate either evidence object or "
    "filesystem history, rerun P128-P132 or dependencies, establish freshness/latest/global/monotonic head truth, prevent coordinated "
    "rollback/replay of mutually consistent inputs, retain a trusted head, authorize startup or mutation, provide CAS, leases, fencing, "
    "TPM/HSM protection, remote witnessing, distributed consensus, HA, native-object recovery, cross-process hot swap, production readiness, "
    "benchmark evidence, novelty evidence, or automatic-control authority."
)

_FIELDS = P131_FIELDS
_P130_FLAGS = (
    "exact_size_verified",
    "exact_sha256_verified",
    "strict_schema_verified",
    "canonical_encoding_verified",
    "retained_identity_verified",
    "p128_evidence_state_verified",
    "p129_contract_verified",
)
_P132_FLAGS = (
    "exact_size_verified",
    "exact_sha256_verified",
    "strict_schema_verified",
    "canonical_encoding_verified",
    "retained_identity_verified",
    "p130_evidence_state_verified",
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
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


RecoveryP130P132CompositionEvidence = make_dataclass(
    "RecoveryP130P132CompositionEvidence",
    [
        *((field, int if kind == "int" else str) for field, kind in _FIELDS),
        ("retained_p131_record_payload_sha256", str),
        ("retained_p131_record_payload_size_bytes", int),
        ("p130_p132_composition_binding_sha256", str),
        ("p130_contract_verified", bool),
        ("p132_contract_verified", bool),
        ("cross_evidence_identity_verified", bool),
        ("evidence_state", str, EVIDENCE_STATE),
        ("automatic_control_allowed", bool, False),
    ],
    frozen=True,
    namespace={"as_dict": lambda self: {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}},
)


def bind_p130_replay_to_p132_retained_identity(
    receipt: RecoveryP129ReceiptVerificationEvidence,
    retained: RecoveryP130ReceiptIdentityVerificationEvidence,
) -> RecoveryP130P132CompositionEvidence:
    """Bind compatible P130 and P132 evidence without granting authority."""
    if not isinstance(receipt, RecoveryP129ReceiptVerificationEvidence):
        raise ValueError("P130 canonical P129 replay evidence has an incompatible type")
    if not isinstance(retained, RecoveryP130ReceiptIdentityVerificationEvidence):
        raise ValueError("P132 retained P131 replay evidence has an incompatible type")

    if receipt.evidence_state != P130_EVIDENCE_STATE:
        raise ValueError("P130 evidence state is incompatible")
    if receipt.automatic_control_allowed is not False:
        raise ValueError("P130 evidence must not grant automatic-control authority")
    if any(getattr(receipt, flag, None) is not True for flag in _P130_FLAGS):
        raise ValueError("P130 verification contract is incomplete")

    if retained.evidence_state != P132_EVIDENCE_STATE:
        raise ValueError("P132 evidence state is incompatible")
    if retained.automatic_control_allowed is not False:
        raise ValueError("P132 evidence must not grant automatic-control authority")
    if any(getattr(retained, flag, None) is not True for flag in _P132_FLAGS):
        raise ValueError("P132 verification contract is incomplete")

    values: dict[str, object] = {}
    for field, kind in _FIELDS:
        parser = _positive_int if kind == "int" else _sha256
        left = parser(getattr(receipt, field, None), field=f"P130 {field}")
        right = parser(getattr(retained, field, None), field=f"P132 {field}")
        if left != right:
            raise ValueError(f"P130/P132 evidence disagrees on {field}")
        values[field] = left

    retained_sha = _sha256(retained.stored_payload_sha256, field="P132 retained P131 record SHA-256")
    retained_size = _positive_int(retained.stored_payload_size_bytes, field="P132 retained P131 record size")
    binding = _canonical_sha(
        {
            **values,
            "retained_p131_record_payload_sha256": retained_sha,
            "retained_p131_record_payload_size_bytes": retained_size,
            "p128_evidence_state": P128_EVIDENCE_STATE,
            "p130_evidence_state": P130_EVIDENCE_STATE,
            "p132_evidence_state": P132_EVIDENCE_STATE,
        }
    )

    return RecoveryP130P132CompositionEvidence(
        **values,
        retained_p131_record_payload_sha256=retained_sha,
        retained_p131_record_payload_size_bytes=retained_size,
        p130_p132_composition_binding_sha256=binding,
        p130_contract_verified=True,
        p132_contract_verified=True,
        cross_evidence_identity_verified=True,
    )
