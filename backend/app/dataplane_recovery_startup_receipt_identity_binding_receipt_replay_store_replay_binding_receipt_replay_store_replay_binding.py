"""Bind verified P85 receipt replay to verified P87 retained-history replay.

P88 composes the independent P85 canonical P84-receipt replay and P87 historical
replay of the retained P86 identity. It fails closed unless both evidence objects
identify the same recovery sequence, lineage, P84 receipt identity, and P83
replay/stored-identity binding, then emits a deterministic read-only composition
binding that also commits to the selected retained P86 record identity.

This is consistency evidence only. Mutually consistent inputs may both be stale,
rolled back, or supplied by an untrusted source, so P88 does not establish
freshness, rollback resistance, persistence trust, or startup authority.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay import (
    EVIDENCE_STATE as P85_EVIDENCE_STATE,
    RecoveryStartupReplayStoredIdentityBindingReceiptReplayEvidence,
)
from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay import (
    EVIDENCE_STATE as P87_EVIDENCE_STATE,
    RecoveryStartupReplayStoredIdentityBindingReceiptReplayIdentityStoreReplayEvidence,
)

EVIDENCE_STATE = (
    "LOCAL_DATA_PLANE_RECOVERY_STARTUP_ADMISSION_STORED_RECEIPT_BINDING_RECEIPT_REPLAY_STORED_IDENTITY_BINDING_"
    "RECEIPT_REPLAY_IDENTITY_STORED_REPLAY_BINDING_VERIFIED"
)
TRUTH_BOUNDARY = (
    "This read-only composition gate proves only that compatible supplied P85 and P87 evidence objects agree on one recovery sequence, "
    "lineage SHA-256, canonical P84 replay-binding receipt SHA-256 and byte length, and P83 replay/stored-identity binding SHA-256, and "
    "that a deterministic binding over those identities, the selected retained P86 record identity, and both evidence-state contracts "
    "was computed during this call. It does not authenticate either evidence object or filesystem history, rerun P85/P87 or dependencies, "
    "establish freshness/latest/global/monotonic head truth, detect coordinated rollback/replay of mutually consistent inputs, retain a "
    "trusted head, authorize startup or mutation, provide CAS, leases, fencing, TPM/HSM protection, remote witnessing, distributed consensus, "
    "HA, native-object recovery, cross-process hot swap, production readiness, benchmark evidence, novelty evidence, or automatic-control authority."
)

_P85_FLAGS = (
    "expected_payload_identity_verified",
    "canonical_receipt_verified",
    "dependency_state_verified",
    "replay_stored_identity_binding_recomputed_verified",
)
_P87_FLAGS = (
    "p86_evidence_state_verified",
    "p86_verification_flags_verified",
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
class RecoveryStartupReplayStoredIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence:
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
    p85_contract_verified: bool
    p87_contract_verified: bool
    cross_evidence_identity_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def bind_recovery_startup_replay_receipt_to_retained_identity_replay(
    receipt: RecoveryStartupReplayStoredIdentityBindingReceiptReplayEvidence,
    stored: RecoveryStartupReplayStoredIdentityBindingReceiptReplayIdentityStoreReplayEvidence,
) -> RecoveryStartupReplayStoredIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence:
    """Bind compatible P85 and P87 replay evidence without granting authority."""
    if not isinstance(receipt, RecoveryStartupReplayStoredIdentityBindingReceiptReplayEvidence):
        raise ValueError("P85 replay-binding receipt evidence has an incompatible type")
    if not isinstance(stored, RecoveryStartupReplayStoredIdentityBindingReceiptReplayIdentityStoreReplayEvidence):
        raise ValueError("P87 retained replay identity evidence has an incompatible type")

    if receipt.evidence_state != P85_EVIDENCE_STATE:
        raise ValueError("P85 replay-binding receipt evidence state is incompatible")
    if receipt.automatic_control_allowed is not False:
        raise ValueError("P85 evidence must not grant automatic-control authority")
    for field in _P85_FLAGS:
        if getattr(receipt, field, None) is not True:
            raise ValueError(f"P85 {field} verification is incomplete")

    if stored.evidence_state != P87_EVIDENCE_STATE:
        raise ValueError("P87 retained replay identity evidence state is incompatible")
    if stored.automatic_control_allowed is not False:
        raise ValueError("P87 evidence must not grant automatic-control authority")
    for field in _P87_FLAGS:
        if getattr(stored, field, None) is not True:
            raise ValueError(f"P87 {field} verification is incomplete")

    receipt_sequence = _positive_int(receipt.sequence, field="P85 sequence")
    stored_sequence = _positive_int(stored.sequence, field="P87 sequence")
    receipt_lineage = _sha256(receipt.lineage_sha256, field="P85 lineage SHA-256")
    stored_lineage = _sha256(stored.lineage_sha256, field="P87 lineage SHA-256")
    receipt_sha = _sha256(receipt.replay_binding_receipt_payload_sha256, field="P85 replay binding receipt payload SHA-256")
    stored_receipt_sha = _sha256(stored.replay_binding_receipt_payload_sha256, field="P87 replay binding receipt payload SHA-256")
    receipt_size = _positive_int(receipt.replay_binding_receipt_payload_size_bytes, field="P85 replay binding receipt payload size")
    stored_receipt_size = _positive_int(stored.replay_binding_receipt_payload_size_bytes, field="P87 replay binding receipt payload size")
    receipt_binding = _sha256(receipt.replay_stored_identity_binding_sha256, field="P85 replay/stored-identity binding SHA-256")
    stored_binding = _sha256(stored.replay_stored_identity_binding_sha256, field="P87 replay/stored-identity binding SHA-256")

    if receipt_sequence != stored_sequence:
        raise ValueError("P85/P87 recovery sequence mismatch")
    if receipt_lineage != stored_lineage:
        raise ValueError("P85/P87 recovery lineage mismatch")
    if receipt_sha != stored_receipt_sha:
        raise ValueError("P85/P87 replay binding receipt SHA-256 mismatch")
    if receipt_size != stored_receipt_size:
        raise ValueError("P85/P87 replay binding receipt byte length mismatch")
    if receipt_binding != stored_binding:
        raise ValueError("P85/P87 replay/stored-identity binding mismatch")

    binding_receipt_sha = _sha256(receipt.binding_receipt_payload_sha256, field="P85 binding receipt payload SHA-256")
    binding_receipt_size = _positive_int(receipt.binding_receipt_payload_size_bytes, field="P85 binding receipt payload size")
    identity_binding = _sha256(receipt.receipt_identity_binding_sha256, field="P85 receipt identity binding SHA-256")
    retained_sha = _sha256(receipt.retained_identity_payload_sha256, field="P85 retained identity payload SHA-256")
    retained_size = _positive_int(receipt.retained_identity_payload_size_bytes, field="P85 retained identity payload size")

    for left, right, label in (
        (binding_receipt_sha, _sha256(stored.binding_receipt_payload_sha256, field="P87 binding receipt payload SHA-256"), "binding receipt SHA-256"),
        (binding_receipt_size, _positive_int(stored.binding_receipt_payload_size_bytes, field="P87 binding receipt payload size"), "binding receipt byte length"),
        (identity_binding, _sha256(stored.receipt_identity_binding_sha256, field="P87 receipt identity binding SHA-256"), "receipt identity binding"),
        (retained_sha, _sha256(stored.retained_identity_payload_sha256, field="P87 retained identity payload SHA-256"), "retained identity SHA-256"),
        (retained_size, _positive_int(stored.retained_identity_payload_size_bytes, field="P87 retained identity payload size"), "retained identity byte length"),
    ):
        if left != right:
            raise ValueError(f"P85/P87 {label} mismatch")

    retained_replay_sha = _sha256(stored.stored_payload_sha256, field="P87 retained replay identity payload SHA-256")
    retained_replay_size = _positive_int(stored.stored_payload_size_bytes, field="P87 retained replay identity payload size")
    binding = _canonical_sha({
        "sequence": receipt_sequence,
        "lineage_sha256": receipt_lineage,
        "binding_receipt_payload_sha256": binding_receipt_sha,
        "binding_receipt_payload_size_bytes": binding_receipt_size,
        "receipt_identity_binding_sha256": identity_binding,
        "retained_identity_payload_sha256": retained_sha,
        "retained_identity_payload_size_bytes": retained_size,
        "replay_stored_identity_binding_sha256": receipt_binding,
        "replay_binding_receipt_payload_sha256": receipt_sha,
        "replay_binding_receipt_payload_size_bytes": receipt_size,
        "retained_replay_identity_payload_sha256": retained_replay_sha,
        "retained_replay_identity_payload_size_bytes": retained_replay_size,
        "p85_evidence_state": P85_EVIDENCE_STATE,
        "p87_evidence_state": P87_EVIDENCE_STATE,
    })

    return RecoveryStartupReplayStoredIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence(
        sequence=receipt_sequence,
        lineage_sha256=receipt_lineage,
        binding_receipt_payload_sha256=binding_receipt_sha,
        binding_receipt_payload_size_bytes=binding_receipt_size,
        receipt_identity_binding_sha256=identity_binding,
        retained_identity_payload_sha256=retained_sha,
        retained_identity_payload_size_bytes=retained_size,
        replay_stored_identity_binding_sha256=receipt_binding,
        replay_binding_receipt_payload_sha256=receipt_sha,
        replay_binding_receipt_payload_size_bytes=receipt_size,
        retained_replay_identity_payload_sha256=retained_replay_sha,
        retained_replay_identity_payload_size_bytes=retained_replay_size,
        replay_retained_identity_binding_sha256=binding,
        p85_contract_verified=True,
        p87_contract_verified=True,
        cross_evidence_identity_verified=True,
    )
