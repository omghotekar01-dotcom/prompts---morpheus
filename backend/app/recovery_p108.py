"""Bind verified P105 canonical replay to verified P107 retained-P106 replay.

P108 composes two independently verified read-only evidence paths and fails closed
unless they identify the same recovery history through the canonical P104 receipt.
The deterministic composition also commits to the selected retained P106 record
identity and dependency evidence-state contracts.

This is consistency evidence only. Mutually consistent inputs may still be stale,
rolled back, or untrusted; P108 grants no startup or mutation authority.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .recovery_p103 import EVIDENCE_STATE as P103_EVIDENCE_STATE
from .recovery_p105 import EVIDENCE_STATE as P105_EVIDENCE_STATE, RecoveryP104ReplayEvidence
from .recovery_p107 import EVIDENCE_STATE as P107_EVIDENCE_STATE, RecoveryP106ReplayEvidence

EVIDENCE_STATE = P107_EVIDENCE_STATE + "_P105_REPLAY_COMPOSITION_BINDING_VERIFIED"
TRUTH_BOUNDARY = (
    "This read-only composition gate proves only that compatible supplied P105 and P107 evidence objects agreed during this call on "
    "one recovery sequence, lineage and inherited receipt/identity bindings through the canonical P104 receipt, and that a deterministic "
    "binding over those shared identities, the selected retained P106 record SHA-256 and byte length, and the P103/P105/P107 evidence-state "
    "contracts was computed. It does not authenticate either evidence object or filesystem history, rerun P105/P107 or dependencies, "
    "establish freshness/latest/global/monotonic head truth, prevent coordinated rollback/replay of mutually consistent inputs, retain "
    "a trusted head, authorize startup or mutation, provide CAS, leases, fencing, TPM/HSM protection, remote witnessing, distributed "
    "consensus, HA, native-object recovery, cross-process hot swap, production readiness, benchmark evidence, novelty evidence, or "
    "automatic-control authority."
)

_FIELDS = (
    ("sequence", "int"),
    ("lineage_sha256", "sha"),
    ("binding_receipt_payload_sha256", "sha"),
    ("binding_receipt_payload_size_bytes", "int"),
    ("receipt_identity_binding_sha256", "sha"),
    ("retained_identity_payload_sha256", "sha"),
    ("retained_identity_payload_size_bytes", "int"),
    ("replay_stored_identity_binding_sha256", "sha"),
    ("replay_binding_receipt_payload_sha256", "sha"),
    ("replay_binding_receipt_payload_size_bytes", "int"),
    ("retained_replay_identity_payload_sha256", "sha"),
    ("retained_replay_identity_payload_size_bytes", "int"),
    ("replay_retained_identity_binding_sha256", "sha"),
    ("replay_retained_identity_binding_receipt_payload_sha256", "sha"),
    ("replay_retained_identity_binding_receipt_payload_size_bytes", "int"),
    ("retained_replay_receipt_identity_payload_sha256", "sha"),
    ("retained_replay_receipt_identity_payload_size_bytes", "int"),
    ("replay_retained_receipt_identity_binding_sha256", "sha"),
    ("replay_retained_receipt_identity_binding_receipt_payload_sha256", "sha"),
    ("replay_retained_receipt_identity_binding_receipt_payload_size_bytes", "int"),
    ("retained_replayed_receipt_identity_payload_sha256", "sha"),
    ("retained_replayed_receipt_identity_payload_size_bytes", "int"),
    ("replayed_receipt_retained_identity_binding_sha256", "sha"),
    ("replayed_receipt_retained_identity_binding_receipt_payload_sha256", "sha"),
    ("replayed_receipt_retained_identity_binding_receipt_payload_size_bytes", "int"),
    ("retained_p101_record_payload_sha256", "sha"),
    ("retained_p101_record_payload_size_bytes", "int"),
    ("p100_p102_composition_binding_sha256", "sha"),
    ("p104_receipt_payload_sha256", "sha"),
    ("p104_receipt_payload_size_bytes", "int"),
)
_P105_FLAGS = (
    "expected_payload_identity_verified",
    "canonical_receipt_verified",
    "dependency_state_verified",
    "p100_p102_composition_binding_recomputed_verified",
)
_P107_FLAGS = (
    "p106_evidence_state_verified",
    "p106_verification_flags_verified",
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
class RecoveryP105P107CompositionEvidence:
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
    p105_contract_verified: bool
    p107_contract_verified: bool
    cross_evidence_identity_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def bind_p105_replay_to_p107_retained_identity(
    receipt: RecoveryP104ReplayEvidence,
    retained: RecoveryP106ReplayEvidence,
) -> RecoveryP105P107CompositionEvidence:
    """Bind compatible P105 and P107 evidence without granting authority."""
    if not isinstance(receipt, RecoveryP104ReplayEvidence):
        raise ValueError("P105 canonical P104 replay evidence has an incompatible type")
    if not isinstance(retained, RecoveryP106ReplayEvidence):
        raise ValueError("P107 retained P106 replay evidence has an incompatible type")

    if receipt.evidence_state != P105_EVIDENCE_STATE:
        raise ValueError("P105 evidence state is incompatible")
    if receipt.p103_evidence_state != P103_EVIDENCE_STATE:
        raise ValueError("P105 embedded P103 evidence state is incompatible")
    if receipt.automatic_control_allowed is not False:
        raise ValueError("P105 evidence must not grant automatic-control authority")
    if any(getattr(receipt, flag, None) is not True for flag in _P105_FLAGS):
        raise ValueError("P105 verification contract is incomplete")

    if retained.evidence_state != P107_EVIDENCE_STATE:
        raise ValueError("P107 evidence state is incompatible")
    if retained.automatic_control_allowed is not False:
        raise ValueError("P107 evidence must not grant automatic-control authority")
    if any(getattr(retained, flag, None) is not True for flag in _P107_FLAGS):
        raise ValueError("P107 verification contract is incomplete")

    values: dict[str, object] = {}
    for field, kind in _FIELDS:
        left_raw = getattr(receipt, field, None)
        right_raw = getattr(retained, field, None)
        parser = _positive_int if kind == "int" else _sha256
        left = parser(left_raw, field=f"P105 {field}")
        right = parser(right_raw, field=f"P107 {field}")
        if left != right:
            raise ValueError(f"P105/P107 evidence disagrees on {field}")
        values[field] = left

    retained_sha = _sha256(retained.stored_payload_sha256, field="P107 retained P106 record SHA-256")
    retained_size = _positive_int(retained.stored_payload_size_bytes, field="P107 retained P106 record size")

    binding = _canonical_sha(
        {
            **values,
            "retained_p106_record_payload_sha256": retained_sha,
            "retained_p106_record_payload_size_bytes": retained_size,
            "p103_evidence_state": P103_EVIDENCE_STATE,
            "p105_evidence_state": P105_EVIDENCE_STATE,
            "p107_evidence_state": P107_EVIDENCE_STATE,
        }
    )

    return RecoveryP105P107CompositionEvidence(
        **values,
        retained_p106_record_payload_sha256=retained_sha,
        retained_p106_record_payload_size_bytes=retained_size,
        p105_p107_composition_binding_sha256=binding,
        p105_contract_verified=True,
        p107_contract_verified=True,
        cross_evidence_identity_verified=True,
    )
