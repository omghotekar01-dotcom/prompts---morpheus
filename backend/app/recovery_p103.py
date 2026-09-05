"""Bind verified P100 canonical replay to verified P102 retained-P101 replay.

P103 composes two independently verified read-only evidence paths and fails closed
unless they identify the same recovery history. The deterministic composition
also commits to the selected retained P101 record identity and dependency state
contracts.

This is consistency evidence only. Mutually consistent inputs may still be stale,
rolled back, or untrusted; P103 grants no startup or mutation authority.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .recovery_p100 import (
    EVIDENCE_STATE as P100_EVIDENCE_STATE,
    RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingReceiptReplayEvidence,
)
from .recovery_p102 import (
    EVIDENCE_STATE as P102_EVIDENCE_STATE,
    RecoveryP101ReplayEvidence,
)
from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding import (
    EVIDENCE_STATE as P98_EVIDENCE_STATE,
)

EVIDENCE_STATE = (
    "LOCAL_DATA_PLANE_RECOVERY_STARTUP_ADMISSION_STORED_RECEIPT_BINDING_RECEIPT_REPLAY_STORED_IDENTITY_BINDING_"
    "RECEIPT_REPLAY_IDENTITY_STORED_REPLAY_BINDING_RECEIPT_REPLAY_VERIFIED_IDENTITY_STORED_REPLAY_BINDING_RECEIPT_REPLAY_"
    "VERIFIED_IDENTITY_STORED_REPLAY_BINDING_VERIFIED_RECEIPT_REPLAY_VERIFIED_IDENTITY_STORED_VERIFIED_BINDING_VERIFIED"
)
TRUTH_BOUNDARY = (
    "This read-only composition gate proves only that compatible supplied P100 and P102 evidence objects agreed during this call on "
    "one recovery sequence, lineage and inherited receipt/identity bindings through the canonical P99 receipt, and that a deterministic "
    "binding over those shared identities, the selected retained P101 record SHA-256 and byte length, and the P100/P102 evidence-state "
    "contracts was computed. It does not authenticate either evidence object or filesystem history, rerun P100/P102 or dependencies, "
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
)
_P100_FLAGS = (
    "expected_payload_identity_verified",
    "canonical_receipt_verified",
    "dependency_state_verified",
    "replayed_receipt_retained_identity_binding_recomputed_verified",
)
_P102_FLAGS = (
    "p101_evidence_state_verified",
    "p101_verification_flags_verified",
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
class RecoveryP100P102CompositionEvidence:
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
    p100_contract_verified: bool
    p102_contract_verified: bool
    cross_evidence_identity_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def bind_p100_replay_to_p102_retained_identity(
    receipt: RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingReceiptReplayEvidence,
    retained: RecoveryP101ReplayEvidence,
) -> RecoveryP100P102CompositionEvidence:
    """Bind compatible P100 and P102 evidence without granting authority."""
    if not isinstance(
        receipt,
        RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingReceiptReplayEvidence,
    ):
        raise ValueError("P100 canonical P99 replay evidence has an incompatible type")
    if not isinstance(retained, RecoveryP101ReplayEvidence):
        raise ValueError("P102 retained P101 replay evidence has an incompatible type")

    if receipt.evidence_state != P100_EVIDENCE_STATE:
        raise ValueError("P100 evidence state is incompatible")
    if receipt.p98_evidence_state != P98_EVIDENCE_STATE:
        raise ValueError("P100 embedded P98 evidence state is incompatible")
    if receipt.automatic_control_allowed is not False:
        raise ValueError("P100 evidence must not grant automatic-control authority")
    if any(getattr(receipt, flag, None) is not True for flag in _P100_FLAGS):
        raise ValueError("P100 verification contract is incomplete")

    if retained.evidence_state != P102_EVIDENCE_STATE:
        raise ValueError("P102 evidence state is incompatible")
    if retained.automatic_control_allowed is not False:
        raise ValueError("P102 evidence must not grant automatic-control authority")
    if any(getattr(retained, flag, None) is not True for flag in _P102_FLAGS):
        raise ValueError("P102 verification contract is incomplete")

    values: dict[str, object] = {}
    for field, kind in _FIELDS:
        left_raw = getattr(receipt, field, None)
        right_raw = getattr(retained, field, None)
        parser = _positive_int if kind == "int" else _sha256
        left = parser(left_raw, field=f"P100 {field}")
        right = parser(right_raw, field=f"P102 {field}")
        if left != right:
            raise ValueError(f"P100/P102 evidence disagrees on {field}")
        values[field] = left

    retained_sha = _sha256(retained.stored_payload_sha256, field="P102 retained P101 record SHA-256")
    retained_size = _positive_int(retained.stored_payload_size_bytes, field="P102 retained P101 record size")

    binding = _canonical_sha(
        {
            **values,
            "retained_p101_record_payload_sha256": retained_sha,
            "retained_p101_record_payload_size_bytes": retained_size,
            "p100_evidence_state": P100_EVIDENCE_STATE,
            "p102_evidence_state": P102_EVIDENCE_STATE,
        }
    )

    return RecoveryP100P102CompositionEvidence(
        **values,
        retained_p101_record_payload_sha256=retained_sha,
        retained_p101_record_payload_size_bytes=retained_size,
        p100_p102_composition_binding_sha256=binding,
        p100_contract_verified=True,
        p102_contract_verified=True,
        cross_evidence_identity_verified=True,
    )