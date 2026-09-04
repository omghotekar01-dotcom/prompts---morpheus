"""Bind verified P80 receipt replay to verified P82 retained-identity replay.

P83 composes the independent P80 canonical binding-receipt replay and P82
historical replay of the retained P81 identity. It fails closed unless both
evidence objects identify the same recovery sequence, lineage, binding-receipt
bytes, and P78 receipt/stored-identity binding, then emits a deterministic
read-only composition binding.

This is consistency evidence only. Mutually consistent replayed inputs may both
be stale or rolled back, so P83 does not establish freshness, latest-head truth,
rollback resistance, persistence trust, or startup authority.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay import (
    EVIDENCE_STATE as P80_EVIDENCE_STATE,
    RecoveryStartupStoredReceiptBindingReceiptReplayEvidence,
)
from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay import (
    EVIDENCE_STATE as P82_EVIDENCE_STATE,
    RecoveryStartupStoredReceiptBindingReceiptReplayIdentityReplayEvidence,
)

EVIDENCE_STATE = "LOCAL_DATA_PLANE_RECOVERY_STARTUP_ADMISSION_STORED_RECEIPT_BINDING_RECEIPT_REPLAY_STORED_IDENTITY_BINDING_VERIFIED"
TRUTH_BOUNDARY = (
    "This read-only composition gate proves only that compatible supplied P80 and P82 evidence objects agree on one recovery sequence, "
    "lineage SHA-256, canonical P79 binding-receipt SHA-256 and byte length, and P78 receipt/stored-identity binding SHA-256, and that a "
    "deterministic binding over those identities and evidence-state contracts was computed during this call. It does not authenticate "
    "either evidence object or filesystem history, rerun P80/P82 or dependencies, establish freshness/latest/global/monotonic head truth, "
    "detect coordinated rollback/replay of mutually consistent inputs, retain a trusted head, authorize startup or mutation, provide CAS, "
    "leases, fencing, TPM/HSM protection, remote witnessing, distributed consensus, HA, native-object recovery, cross-process hot swap, "
    "production readiness, benchmark evidence, novelty evidence, or automatic-control authority."
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
class RecoveryStartupStoredReceiptBindingReceiptReplayStoredIdentityBindingEvidence:
    sequence: int
    lineage_sha256: str
    binding_receipt_payload_sha256: str
    binding_receipt_payload_size_bytes: int
    receipt_identity_binding_sha256: str
    retained_identity_payload_sha256: str
    retained_identity_payload_size_bytes: int
    replay_stored_identity_binding_sha256: str
    p80_contract_verified: bool
    p82_contract_verified: bool
    cross_evidence_identity_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def bind_recovery_startup_binding_receipt_replay_to_stored_identity_replay(
    receipt: RecoveryStartupStoredReceiptBindingReceiptReplayEvidence,
    stored: RecoveryStartupStoredReceiptBindingReceiptReplayIdentityReplayEvidence,
) -> RecoveryStartupStoredReceiptBindingReceiptReplayStoredIdentityBindingEvidence:
    """Bind compatible P80 and P82 replay evidence without granting authority."""
    if not isinstance(receipt, RecoveryStartupStoredReceiptBindingReceiptReplayEvidence):
        raise ValueError("P80 binding-receipt replay evidence has an incompatible type")
    if not isinstance(stored, RecoveryStartupStoredReceiptBindingReceiptReplayIdentityReplayEvidence):
        raise ValueError("P82 retained-identity replay evidence has an incompatible type")

    if receipt.evidence_state != P80_EVIDENCE_STATE:
        raise ValueError("P80 binding-receipt replay evidence state is incompatible")
    if receipt.automatic_control_allowed is not False:
        raise ValueError("P80 evidence must not grant automatic-control authority")
    for field in (
        "expected_payload_identity_verified", "canonical_receipt_verified",
        "dependency_state_verified", "receipt_identity_binding_recomputed_verified",
    ):
        if getattr(receipt, field) is not True:
            raise ValueError(f"P80 {field} verification is incomplete")

    if stored.evidence_state != P82_EVIDENCE_STATE:
        raise ValueError("P82 retained-identity replay evidence state is incompatible")
    if stored.automatic_control_allowed is not False:
        raise ValueError("P82 evidence must not grant automatic-control authority")
    for field in (
        "expected_payload_identity_verified", "canonical_record_verified",
        "p80_evidence_state_verified", "semantic_identity_verified",
    ):
        if getattr(stored, field) is not True:
            raise ValueError(f"P82 {field} verification is incomplete")

    receipt_sequence = _positive_int(receipt.sequence, field="P80 sequence")
    stored_sequence = _positive_int(stored.sequence, field="P82 sequence")
    receipt_lineage = _sha256(receipt.lineage_sha256, field="P80 lineage SHA-256")
    stored_lineage = _sha256(stored.lineage_sha256, field="P82 lineage SHA-256")
    receipt_sha = _sha256(receipt.binding_receipt_payload_sha256, field="P80 binding receipt payload SHA-256")
    stored_receipt_sha = _sha256(stored.binding_receipt_payload_sha256, field="P82 binding receipt payload SHA-256")
    receipt_size = _positive_int(receipt.binding_receipt_payload_size_bytes, field="P80 binding receipt payload size")
    stored_receipt_size = _positive_int(stored.binding_receipt_payload_size_bytes, field="P82 binding receipt payload size")
    receipt_binding = _sha256(receipt.receipt_identity_binding_sha256, field="P80 receipt identity binding SHA-256")
    stored_binding = _sha256(stored.receipt_identity_binding_sha256, field="P82 receipt identity binding SHA-256")
    retained_sha = _sha256(stored.stored_payload_sha256, field="P82 retained identity payload SHA-256")
    retained_size = _positive_int(stored.stored_payload_size_bytes, field="P82 retained identity payload size")

    if receipt_sequence != stored_sequence:
        raise ValueError("P80/P82 recovery sequence mismatch")
    if receipt_lineage != stored_lineage:
        raise ValueError("P80/P82 recovery lineage mismatch")
    if receipt_sha != stored_receipt_sha:
        raise ValueError("P80/P82 binding receipt SHA-256 mismatch")
    if receipt_size != stored_receipt_size:
        raise ValueError("P80/P82 binding receipt byte length mismatch")
    if receipt_binding != stored_binding:
        raise ValueError("P80/P82 receipt identity binding mismatch")

    binding = _canonical_sha({
        "sequence": receipt_sequence,
        "lineage_sha256": receipt_lineage,
        "binding_receipt_payload_sha256": receipt_sha,
        "binding_receipt_payload_size_bytes": receipt_size,
        "receipt_identity_binding_sha256": receipt_binding,
        "retained_identity_payload_sha256": retained_sha,
        "retained_identity_payload_size_bytes": retained_size,
        "p80_evidence_state": P80_EVIDENCE_STATE,
        "p82_evidence_state": P82_EVIDENCE_STATE,
    })

    return RecoveryStartupStoredReceiptBindingReceiptReplayStoredIdentityBindingEvidence(
        sequence=receipt_sequence,
        lineage_sha256=receipt_lineage,
        binding_receipt_payload_sha256=receipt_sha,
        binding_receipt_payload_size_bytes=receipt_size,
        receipt_identity_binding_sha256=receipt_binding,
        retained_identity_payload_sha256=retained_sha,
        retained_identity_payload_size_bytes=retained_size,
        replay_stored_identity_binding_sha256=binding,
        p80_contract_verified=True,
        p82_contract_verified=True,
        cross_evidence_identity_verified=True,
    )
