"""Bind replayed startup-admission receipt evidence to its replayed stored identity.

P78 composes the independent consumer-side checks from P75 and P77. A caller
supplies one verified P75 canonical-receipt replay and one verified P77 replay of
the locally persisted P76 identity record. This gate fails closed unless both
objects identify the same recovery sequence, lineage, receipt bytes, and P73
admission binding, then emits a deterministic read-only binding over those two
evidence contracts.

This is composition consistency only. Coordinated replay or replacement of both
inputs can remain internally consistent, so P78 does not establish freshness,
latest-head truth, rollback resistance, or startup authority.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .dataplane_recovery_startup_receipt_identity_replay import (
    EVIDENCE_STATE as P77_EVIDENCE_STATE,
    RecoveryStartupReceiptIdentityReplayEvidence,
)
from .dataplane_recovery_startup_receipt_replay import (
    EVIDENCE_STATE as P75_EVIDENCE_STATE,
    RecoveryStartupAdmissionReceiptReplayEvidence,
)

EVIDENCE_STATE = "LOCAL_DATA_PLANE_RECOVERY_STARTUP_ADMISSION_STORED_RECEIPT_BINDING_VERIFIED"
TRUTH_BOUNDARY = (
    "This gate proves only that compatible supplied P75 and P77 evidence objects agree on one recovery sequence, lineage SHA-256, "
    "canonical receipt payload SHA-256 and byte length, and P73 admission-binding SHA-256, and that a deterministic binding over "
    "those identities and evidence-state contracts was computed during this call. It does not authenticate either evidence object, "
    "rerun P75/P77 or their dependencies, prove freshness/latest/global/monotonic head truth, detect coordinated rollback/replay of "
    "mutually consistent inputs, retain a trusted head, authorize startup or mutation, provide CAS, leases, fencing, TPM/HSM protection, "
    "remote witnessing, distributed consensus, HA, native-object recovery, cross-process hot swap, production readiness, benchmark "
    "evidence, novelty evidence, or automatic-control authority."
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
    raw = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class RecoveryStartupStoredReceiptBindingEvidence:
    sequence: int
    lineage_sha256: str
    receipt_payload_sha256: str
    receipt_payload_size_bytes: int
    admission_binding_sha256: str
    stored_identity_payload_sha256: str
    stored_identity_payload_size_bytes: int
    receipt_identity_binding_sha256: str
    p75_contract_verified: bool
    p77_contract_verified: bool
    cross_evidence_identity_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def bind_recovery_startup_receipt_to_stored_identity(
    receipt: RecoveryStartupAdmissionReceiptReplayEvidence,
    stored: RecoveryStartupReceiptIdentityReplayEvidence,
) -> RecoveryStartupStoredReceiptBindingEvidence:
    """Bind compatible P75 receipt replay to compatible P77 stored-identity replay."""
    if not isinstance(receipt, RecoveryStartupAdmissionReceiptReplayEvidence):
        raise ValueError("P75 receipt-replay evidence has an incompatible type")
    if not isinstance(stored, RecoveryStartupReceiptIdentityReplayEvidence):
        raise ValueError("P77 stored-identity replay evidence has an incompatible type")

    if receipt.evidence_state != P75_EVIDENCE_STATE:
        raise ValueError("P75 receipt-replay evidence state is incompatible")
    if receipt.automatic_control_allowed is not False:
        raise ValueError("P75 receipt-replay evidence must not grant automatic-control authority")
    if receipt.expected_payload_identity_verified is not True:
        raise ValueError("P75 expected-payload identity verification is incomplete")
    if receipt.canonical_receipt_verified is not True:
        raise ValueError("P75 canonical-receipt verification is incomplete")
    if receipt.admission_binding_recomputed_verified is not True:
        raise ValueError("P75 admission-binding recomputation is incomplete")
    if receipt.dependency_states_verified is not True:
        raise ValueError("P75 dependency-state verification is incomplete")

    if stored.evidence_state != P77_EVIDENCE_STATE:
        raise ValueError("P77 stored-identity replay evidence state is incompatible")
    if stored.automatic_control_allowed is not False:
        raise ValueError("P77 stored-identity replay evidence must not grant automatic-control authority")
    if stored.expected_payload_identity_verified is not True:
        raise ValueError("P77 expected-payload identity verification is incomplete")
    if stored.canonical_record_verified is not True:
        raise ValueError("P77 canonical-record verification is incomplete")
    if stored.semantic_identity_verified is not True:
        raise ValueError("P77 semantic-identity verification is incomplete")

    receipt_sequence = _positive_int(receipt.sequence, field="P75 sequence")
    stored_sequence = _positive_int(stored.sequence, field="P77 sequence")
    receipt_lineage = _sha256(receipt.lineage_sha256, field="P75 lineage SHA-256")
    stored_lineage = _sha256(stored.lineage_sha256, field="P77 lineage SHA-256")
    receipt_sha = _sha256(
        receipt.receipt_payload_sha256, field="P75 receipt payload SHA-256"
    )
    stored_receipt_sha = _sha256(
        stored.receipt_payload_sha256, field="P77 receipt payload SHA-256"
    )
    receipt_size = _positive_int(
        receipt.receipt_payload_size_bytes, field="P75 receipt payload size"
    )
    stored_receipt_size = _positive_int(
        stored.receipt_payload_size_bytes, field="P77 receipt payload size"
    )
    receipt_admission = _sha256(
        receipt.admission_binding_sha256, field="P75 admission binding SHA-256"
    )
    stored_admission = _sha256(
        stored.admission_binding_sha256, field="P77 admission binding SHA-256"
    )
    stored_identity_sha = _sha256(
        stored.stored_payload_sha256, field="P77 stored identity payload SHA-256"
    )
    stored_identity_size = _positive_int(
        stored.stored_payload_size_bytes, field="P77 stored identity payload size"
    )

    if receipt_sequence != stored_sequence:
        raise ValueError("P75/P77 startup-admission sequence mismatch")
    if receipt_lineage != stored_lineage:
        raise ValueError("P75/P77 startup-admission lineage mismatch")
    if receipt_sha != stored_receipt_sha:
        raise ValueError("P75/P77 startup-admission receipt SHA-256 mismatch")
    if receipt_size != stored_receipt_size:
        raise ValueError("P75/P77 startup-admission receipt byte length mismatch")
    if receipt_admission != stored_admission:
        raise ValueError("P75/P77 startup-admission binding mismatch")

    binding = _canonical_sha(
        {
            "sequence": receipt_sequence,
            "lineage_sha256": receipt_lineage,
            "receipt_payload_sha256": receipt_sha,
            "receipt_payload_size_bytes": receipt_size,
            "admission_binding_sha256": receipt_admission,
            "stored_identity_payload_sha256": stored_identity_sha,
            "stored_identity_payload_size_bytes": stored_identity_size,
            "p75_evidence_state": P75_EVIDENCE_STATE,
            "p77_evidence_state": P77_EVIDENCE_STATE,
        }
    )

    return RecoveryStartupStoredReceiptBindingEvidence(
        sequence=receipt_sequence,
        lineage_sha256=receipt_lineage,
        receipt_payload_sha256=receipt_sha,
        receipt_payload_size_bytes=receipt_size,
        admission_binding_sha256=receipt_admission,
        stored_identity_payload_sha256=stored_identity_sha,
        stored_identity_payload_size_bytes=stored_identity_size,
        receipt_identity_binding_sha256=binding,
        p75_contract_verified=True,
        p77_contract_verified=True,
        cross_evidence_identity_verified=True,
    )
