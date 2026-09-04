"""Canonicalize P73 startup-admission evidence into a portable audit receipt.

P74 closes a narrow evidence-portability seam. P73 binds the exact current
recovery identity to a repeatedly observed local anchor, but its dataclass is an
in-process object. P74 validates the complete P73 contract and emits strict
canonical JSON bytes plus their SHA-256 identity so the admission evidence can
be compared, logged, or transported without depending on Python object layout.

This gate does not persist the receipt, authenticate it, authorize startup, or
upgrade P73's local observations into a monotonic or atomic source of truth.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .dataplane_recovery_startup_admission import (
    EVIDENCE_STATE as P73_EVIDENCE_STATE,
    RecoveryStartupAdmissionEvidence,
)

EVIDENCE_STATE = "LOCAL_DATA_PLANE_RECOVERY_STARTUP_ADMISSION_RECEIPT_VERIFIED"
TRUTH_BOUNDARY = (
    "This gate proves only that compatible, fully verified supplied P73 evidence was encoded as strict canonical JSON and "
    "bound to an exact SHA-256 byte identity. It does not rerun P73 or its dependencies, authenticate the evidence or receipt, "
    "persist or independently retain it, establish latest/global/monotonic head truth, prevent rollback, provide atomicity, "
    "authorize startup or mutation, or provide CAS, leases, fencing, TPM/HSM protection, remote witnessing, distributed "
    "consensus, HA, native-object recovery, cross-process hot swap, production readiness, benchmark evidence, novelty evidence, "
    "or automatic-control authority."
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


@dataclass(frozen=True)
class RecoveryStartupAdmissionReceiptEvidence:
    sequence: int
    lineage_sha256: str
    admission_binding_sha256: str
    receipt_payload_sha256: str
    receipt_payload_size_bytes: int
    receipt_payload_utf8: bytes
    canonical_receipt_verified: bool
    exact_payload_identity_verified: bool
    p73_evidence_state: str
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "lineage_sha256": self.lineage_sha256,
            "admission_binding_sha256": self.admission_binding_sha256,
            "receipt_payload_sha256": self.receipt_payload_sha256,
            "receipt_payload_size_bytes": self.receipt_payload_size_bytes,
            "canonical_receipt_verified": self.canonical_receipt_verified,
            "exact_payload_identity_verified": self.exact_payload_identity_verified,
            "p73_evidence_state": self.p73_evidence_state,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def encode_recovery_startup_admission_receipt(
    admission_evidence: RecoveryStartupAdmissionEvidence,
) -> RecoveryStartupAdmissionReceiptEvidence:
    """Validate P73 and emit its minimal canonical portable receipt."""
    if admission_evidence.evidence_state != P73_EVIDENCE_STATE:
        raise ValueError("P73 startup-admission evidence has an incompatible evidence state")
    if not (
        admission_evidence.recovery_identity_match_verified
        and admission_evidence.repeated_anchor_identity_bound
    ):
        raise ValueError("P73 startup-admission evidence is not fully verified")
    if admission_evidence.automatic_control_allowed:
        raise ValueError("P73 startup-admission evidence cannot authorize automatic control")

    sequence = _positive_int(admission_evidence.sequence, field="P73 sequence")
    lineage = _sha256(admission_evidence.lineage_sha256, field="P73 lineage SHA-256")
    p67_binding = _sha256(
        admission_evidence.p67_binding_sha256, field="P73 P67 binding SHA-256"
    )
    observed_sha = _sha256(
        admission_evidence.observed_anchor_payload_sha256,
        field="P73 observed anchor payload SHA-256",
    )
    observed_size = _positive_int(
        admission_evidence.observed_anchor_payload_size_bytes,
        field="P73 observed anchor payload size",
    )
    admission_binding = _sha256(
        admission_evidence.admission_binding_sha256,
        field="P73 admission binding SHA-256",
    )
    if not isinstance(admission_evidence.p67_evidence_state, str) or not admission_evidence.p67_evidence_state:
        raise ValueError("P73 P67 evidence state must be a non-empty string")
    if not isinstance(admission_evidence.p72_evidence_state, str) or not admission_evidence.p72_evidence_state:
        raise ValueError("P73 P72 evidence state must be a non-empty string")

    payload = {
        "admission_binding_sha256": admission_binding,
        "lineage_sha256": lineage,
        "observed_anchor_payload_sha256": observed_sha,
        "observed_anchor_payload_size_bytes": observed_size,
        "p67_binding_sha256": p67_binding,
        "p67_evidence_state": admission_evidence.p67_evidence_state,
        "p72_evidence_state": admission_evidence.p72_evidence_state,
        "sequence": sequence,
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()

    # Parse the exact emitted bytes back and require semantic equality. This is
    # intentionally local canonicalization evidence, not authenticity.
    decoded = json.loads(encoded.decode("utf-8"))
    if decoded != payload:
        raise ValueError("canonical startup-admission receipt readback mismatch")

    return RecoveryStartupAdmissionReceiptEvidence(
        sequence=sequence,
        lineage_sha256=lineage,
        admission_binding_sha256=admission_binding,
        receipt_payload_sha256=digest,
        receipt_payload_size_bytes=len(encoded),
        receipt_payload_utf8=encoded,
        canonical_receipt_verified=True,
        exact_payload_identity_verified=True,
        p73_evidence_state=admission_evidence.evidence_state,
    )
