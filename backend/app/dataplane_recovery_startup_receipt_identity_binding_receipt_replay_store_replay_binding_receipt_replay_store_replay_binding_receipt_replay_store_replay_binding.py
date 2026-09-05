"""Bind verified P90 canonical replay to verified P92 retained-history replay.

P93 composes two independently verified read-only evidence paths and fails closed
unless they identify the same recovery sequence, lineage, inherited receipt and
binding identities, and canonical P89 replay/retained-identity binding receipt.
The resulting deterministic binding additionally commits to the selected retained
P91 record identity and both dependency evidence-state contracts.

This is consistency evidence only. Mutually consistent inputs may still be stale,
rolled back, or supplied by an untrusted source; P93 grants no startup or mutation
authority.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay import (
    EVIDENCE_STATE as P90_EVIDENCE_STATE,
    RecoveryStartupReplayRetainedIdentityBindingReceiptReplayEvidence,
)
from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay import (
    EVIDENCE_STATE as P92_EVIDENCE_STATE,
    RecoveryStartupReplayRetainedIdentityBindingReceiptReplayIdentityStoreReplayEvidence,
)

EVIDENCE_STATE = (
    "LOCAL_DATA_PLANE_RECOVERY_STARTUP_ADMISSION_STORED_RECEIPT_BINDING_RECEIPT_REPLAY_STORED_IDENTITY_BINDING_"
    "RECEIPT_REPLAY_IDENTITY_STORED_REPLAY_BINDING_RECEIPT_REPLAY_VERIFIED_IDENTITY_STORED_REPLAY_BINDING_VERIFIED"
)
TRUTH_BOUNDARY = (
    "This read-only composition gate proves only that compatible supplied P90 and P92 evidence objects agreed during this call on one recovery "
    "sequence, lineage SHA-256, inherited receipt/identity bindings, canonical P89 replay/retained-identity binding receipt SHA-256 and byte length, "
    "and that a deterministic binding over those identities, the selected retained P91 record identity, and both evidence-state contracts was "
    "computed. It does not authenticate either evidence object or filesystem history, rerun P90/P92 or dependencies, establish freshness/latest/"
    "global/monotonic head truth, detect coordinated rollback/replay of mutually consistent inputs, retain a trusted head, authorize startup or "
    "mutation, provide CAS, leases, fencing, TPM/HSM protection, remote witnessing, distributed consensus, HA, native-object recovery, cross-process "
    "hot swap, production readiness, benchmark evidence, novelty evidence, or automatic-control authority."
)

_P90_FLAGS = (
    "expected_payload_identity_verified",
    "canonical_receipt_verified",
    "dependency_state_verified",
    "replay_retained_identity_binding_recomputed_verified",
)
_P92_FLAGS = (
    "p91_evidence_state_verified",
    "p91_verification_flags_verified",
    "exact_payload_identity_verified",
    "canonical_record_verified",
    "semantic_agreement_verified",
)


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


def _canonical_sha(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class RecoveryStartupReplayRetainedIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence:
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
    p90_contract_verified: bool
    p92_contract_verified: bool
    cross_evidence_identity_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def bind_recovery_startup_replay_retained_receipt_to_retained_identity_replay(
    receipt: RecoveryStartupReplayRetainedIdentityBindingReceiptReplayEvidence,
    stored: RecoveryStartupReplayRetainedIdentityBindingReceiptReplayIdentityStoreReplayEvidence,
) -> RecoveryStartupReplayRetainedIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence:
    """Bind compatible P90 and P92 evidence without granting authority."""
    if not isinstance(receipt, RecoveryStartupReplayRetainedIdentityBindingReceiptReplayEvidence):
        raise ValueError("P90 replay/retained-identity receipt evidence has an incompatible type")
    if not isinstance(stored, RecoveryStartupReplayRetainedIdentityBindingReceiptReplayIdentityStoreReplayEvidence):
        raise ValueError("P92 retained P91 identity replay evidence has an incompatible type")

    if receipt.evidence_state != P90_EVIDENCE_STATE:
        raise ValueError("P90 evidence state is incompatible")
    if receipt.automatic_control_allowed is not False:
        raise ValueError("P90 evidence must not grant automatic-control authority")
    if any(getattr(receipt, flag, None) is not True for flag in _P90_FLAGS):
        raise ValueError("P90 verification flags are incomplete")

    if stored.evidence_state != P92_EVIDENCE_STATE:
        raise ValueError("P92 evidence state is incompatible")
    if stored.automatic_control_allowed is not False:
        raise ValueError("P92 evidence must not grant automatic-control authority")
    if any(getattr(stored, flag, None) is not True for flag in _P92_FLAGS):
        raise ValueError("P92 verification flags are incomplete")

    shared = (
        ("sequence", _positive_int),
        ("lineage_sha256", _sha256),
        ("binding_receipt_payload_sha256", _sha256),
        ("binding_receipt_payload_size_bytes", _positive_int),
        ("receipt_identity_binding_sha256", _sha256),
        ("retained_identity_payload_sha256", _sha256),
        ("retained_identity_payload_size_bytes", _positive_int),
        ("replay_stored_identity_binding_sha256", _sha256),
        ("replay_binding_receipt_payload_sha256", _sha256),
        ("replay_binding_receipt_payload_size_bytes", _positive_int),
        ("retained_replay_identity_payload_sha256", _sha256),
        ("retained_replay_identity_payload_size_bytes", _positive_int),
        ("replay_retained_identity_binding_sha256", _sha256),
        ("replay_retained_identity_binding_receipt_payload_sha256", _sha256),
        ("replay_retained_identity_binding_receipt_payload_size_bytes", _positive_int),
    )
    values: dict[str, object] = {}
    for field, validator in shared:
        left = validator(getattr(receipt, field), field=f"P90 {field}")
        right = validator(getattr(stored, field), field=f"P92 {field}")
        if left != right:
            raise ValueError(f"P90/P92 {field} mismatch")
        values[field] = left

    retained_sha = _sha256(stored.stored_payload_sha256, field="P92 retained P91 record SHA-256")
    retained_size = _positive_int(stored.stored_payload_size_bytes, field="P92 retained P91 record size")
    binding = _canonical_sha({
        **values,
        "retained_replay_receipt_identity_payload_sha256": retained_sha,
        "retained_replay_receipt_identity_payload_size_bytes": retained_size,
        "p90_evidence_state": P90_EVIDENCE_STATE,
        "p92_evidence_state": P92_EVIDENCE_STATE,
    })

    return RecoveryStartupReplayRetainedIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence(
        **values,
        retained_replay_receipt_identity_payload_sha256=retained_sha,
        retained_replay_receipt_identity_payload_size_bytes=retained_size,
        replay_retained_receipt_identity_binding_sha256=binding,
        p90_contract_verified=True,
        p92_contract_verified=True,
        cross_evidence_identity_verified=True,
    )
