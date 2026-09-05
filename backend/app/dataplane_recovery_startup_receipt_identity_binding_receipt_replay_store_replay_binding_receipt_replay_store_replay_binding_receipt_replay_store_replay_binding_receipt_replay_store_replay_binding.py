"""Bind verified P95 canonical P94 replay to verified P97 retained-P96 replay.

P98 composes two independently verified read-only evidence paths and fails closed
unless they identify the same recovery sequence, lineage, inherited receipt and
binding identities, and canonical P94 replay/retained-receipt binding receipt.
The resulting deterministic binding additionally commits to the selected retained
P96 record identity and both dependency evidence-state contracts.

This is consistency evidence only. Mutually consistent inputs may still be stale,
rolled back, or supplied by an untrusted source; P98 grants no startup or mutation
authority.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay import (
    EVIDENCE_STATE as P95_EVIDENCE_STATE,
    RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayEvidence,
)
from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay import (
    EVIDENCE_STATE as P97_EVIDENCE_STATE,
    RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoreReplayEvidence,
)

EVIDENCE_STATE = (
    "LOCAL_DATA_PLANE_RECOVERY_STARTUP_ADMISSION_STORED_RECEIPT_BINDING_RECEIPT_REPLAY_STORED_IDENTITY_BINDING_"
    "RECEIPT_REPLAY_IDENTITY_STORED_REPLAY_BINDING_RECEIPT_REPLAY_VERIFIED_IDENTITY_STORED_REPLAY_BINDING_RECEIPT_REPLAY_"
    "VERIFIED_IDENTITY_STORED_REPLAY_BINDING_VERIFIED"
)
TRUTH_BOUNDARY = (
    "This read-only composition gate proves only that compatible supplied P95 and P97 evidence objects agreed during this call on one recovery "
    "sequence, lineage SHA-256, inherited receipt/identity bindings, canonical P94 replay/retained-receipt binding receipt SHA-256 and byte length, "
    "and that a deterministic binding over those identities, the selected retained P96 record identity, and both evidence-state contracts was "
    "computed. It does not authenticate either evidence object or filesystem history, rerun P95/P97 or dependencies, establish freshness/latest/"
    "global/monotonic head truth, detect coordinated rollback/replay of mutually consistent inputs, retain a trusted head, authorize startup or "
    "mutation, provide CAS, leases, fencing, TPM/HSM protection, remote witnessing, distributed consensus, HA, native-object recovery, cross-process "
    "hot swap, production readiness, benchmark evidence, novelty evidence, or automatic-control authority."
)

_P95_FLAGS = (
    "expected_payload_identity_verified",
    "canonical_receipt_verified",
    "dependency_state_verified",
    "replay_retained_receipt_identity_binding_recomputed_verified",
)
_P97_FLAGS = (
    "p96_evidence_state_verified",
    "p96_verification_flags_verified",
    "exact_payload_identity_verified",
    "canonical_record_verified",
    "semantic_agreement_verified",
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
class RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence:
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
    p95_contract_verified: bool
    p97_contract_verified: bool
    cross_evidence_identity_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def bind_recovery_startup_replayed_receipt_to_retained_replay_identity(
    receipt: RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayEvidence,
    stored: RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoreReplayEvidence,
) -> RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence:
    """Bind compatible P95 and P97 evidence without granting authority."""
    if not isinstance(receipt, RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayEvidence):
        raise ValueError("P95 replayed P94 receipt evidence has an incompatible type")
    if not isinstance(stored, RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoreReplayEvidence):
        raise ValueError("P97 retained P96 identity replay evidence has an incompatible type")

    if receipt.evidence_state != P95_EVIDENCE_STATE:
        raise ValueError("P95 evidence state is incompatible")
    if receipt.automatic_control_allowed is not False:
        raise ValueError("P95 evidence must not grant automatic-control authority")
    if any(getattr(receipt, flag, None) is not True for flag in _P95_FLAGS):
        raise ValueError("P95 verification flags are incomplete")

    if stored.evidence_state != P97_EVIDENCE_STATE:
        raise ValueError("P97 evidence state is incompatible")
    if stored.automatic_control_allowed is not False:
        raise ValueError("P97 evidence must not grant automatic-control authority")
    if any(getattr(stored, flag, None) is not True for flag in _P97_FLAGS):
        raise ValueError("P97 verification flags are incomplete")

    values: dict[str, object] = {}
    for field, kind in _FIELDS:
        validator = _positive_int if kind == "int" else _sha256
        left = validator(getattr(receipt, field, None), field=f"P95 {field}")
        right = validator(getattr(stored, field, None), field=f"P97 {field}")
        if left != right:
            raise ValueError(f"P95/P97 {field} mismatch")
        values[field] = left

    retained_sha = _sha256(stored.stored_payload_sha256, field="P97 retained P96 record SHA-256")
    retained_size = _positive_int(stored.stored_payload_size_bytes, field="P97 retained P96 record size")

    binding = _canonical_sha({
        **values,
        "retained_replayed_receipt_identity_payload_sha256": retained_sha,
        "retained_replayed_receipt_identity_payload_size_bytes": retained_size,
        "p95_evidence_state": P95_EVIDENCE_STATE,
        "p97_evidence_state": P97_EVIDENCE_STATE,
    })

    return RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence(
        **values,
        retained_replayed_receipt_identity_payload_sha256=retained_sha,
        retained_replayed_receipt_identity_payload_size_bytes=retained_size,
        replayed_receipt_retained_identity_binding_sha256=binding,
        p95_contract_verified=True,
        p97_contract_verified=True,
        cross_evidence_identity_verified=True,
    )
