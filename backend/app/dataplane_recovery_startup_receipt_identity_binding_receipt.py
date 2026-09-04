"""Canonicalize P78 startup receipt/stored-identity binding evidence.

P79 closes a narrow evidence-portability seam. P78 binds independently replayed
P75 canonical startup-admission receipt evidence to independently replayed P77
stored-identity evidence, but the resulting dataclass remains an in-process
object. P79 validates the full P78 contract and emits strict canonical JSON bytes
plus their exact SHA-256 identity for later comparison or audit replay.

This is portable composition evidence only. It is deliberately read-only and
does not authenticate or persist the receipt, establish freshness or a
latest/monotonic head, or authorize startup or mutation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .dataplane_recovery_startup_receipt_identity_binding import (
    EVIDENCE_STATE as P78_EVIDENCE_STATE,
    RecoveryStartupStoredReceiptBindingEvidence,
)

EVIDENCE_STATE = "LOCAL_DATA_PLANE_RECOVERY_STARTUP_ADMISSION_STORED_RECEIPT_BINDING_RECEIPT_VERIFIED"
TRUTH_BOUNDARY = (
    "This gate proves only that compatible, fully verified supplied P78 evidence was encoded as strict canonical JSON and bound "
    "to an exact SHA-256 byte identity during this call. It does not rerun P78 or P75/P77 and their dependencies, authenticate or "
    "persist the evidence/receipt, establish freshness/latest/global/monotonic head truth, prevent coordinated rollback or replay, "
    "provide atomicity after return, authorize startup or mutation, provide CAS, leases, fencing, TPM/HSM protection, remote "
    "witnessing, distributed consensus, HA, native-object recovery, cross-process hot swap, production readiness, benchmark "
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


@dataclass(frozen=True)
class RecoveryStartupStoredReceiptBindingReceiptEvidence:
    sequence: int
    lineage_sha256: str
    receipt_payload_sha256: str
    receipt_payload_size_bytes: int
    admission_binding_sha256: str
    stored_identity_payload_sha256: str
    stored_identity_payload_size_bytes: int
    receipt_identity_binding_sha256: str
    binding_receipt_payload_sha256: str
    binding_receipt_payload_size_bytes: int
    binding_receipt_payload_utf8: bytes
    canonical_receipt_verified: bool
    exact_payload_identity_verified: bool
    p78_evidence_state: str
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "lineage_sha256": self.lineage_sha256,
            "receipt_payload_sha256": self.receipt_payload_sha256,
            "receipt_payload_size_bytes": self.receipt_payload_size_bytes,
            "admission_binding_sha256": self.admission_binding_sha256,
            "stored_identity_payload_sha256": self.stored_identity_payload_sha256,
            "stored_identity_payload_size_bytes": self.stored_identity_payload_size_bytes,
            "receipt_identity_binding_sha256": self.receipt_identity_binding_sha256,
            "binding_receipt_payload_sha256": self.binding_receipt_payload_sha256,
            "binding_receipt_payload_size_bytes": self.binding_receipt_payload_size_bytes,
            "canonical_receipt_verified": self.canonical_receipt_verified,
            "exact_payload_identity_verified": self.exact_payload_identity_verified,
            "p78_evidence_state": self.p78_evidence_state,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def encode_recovery_startup_stored_receipt_binding_receipt(
    binding_evidence: RecoveryStartupStoredReceiptBindingEvidence,
) -> RecoveryStartupStoredReceiptBindingReceiptEvidence:
    """Validate P78 and emit a minimal canonical portable binding receipt."""
    if not isinstance(binding_evidence, RecoveryStartupStoredReceiptBindingEvidence):
        raise ValueError("P78 stored-receipt binding evidence has an incompatible type")
    if binding_evidence.evidence_state != P78_EVIDENCE_STATE:
        raise ValueError("P78 stored-receipt binding evidence state is incompatible")
    if binding_evidence.automatic_control_allowed is not False:
        raise ValueError("P78 stored-receipt binding evidence cannot authorize automatic control")
    if binding_evidence.p75_contract_verified is not True:
        raise ValueError("P78 P75 contract verification is incomplete")
    if binding_evidence.p77_contract_verified is not True:
        raise ValueError("P78 P77 contract verification is incomplete")
    if binding_evidence.cross_evidence_identity_verified is not True:
        raise ValueError("P78 cross-evidence identity verification is incomplete")

    sequence = _positive_int(binding_evidence.sequence, field="P78 sequence")
    lineage = _sha256(binding_evidence.lineage_sha256, field="P78 lineage SHA-256")
    receipt_sha = _sha256(
        binding_evidence.receipt_payload_sha256, field="P78 receipt payload SHA-256"
    )
    receipt_size = _positive_int(
        binding_evidence.receipt_payload_size_bytes, field="P78 receipt payload size"
    )
    admission_binding = _sha256(
        binding_evidence.admission_binding_sha256, field="P78 admission binding SHA-256"
    )
    stored_sha = _sha256(
        binding_evidence.stored_identity_payload_sha256,
        field="P78 stored identity payload SHA-256",
    )
    stored_size = _positive_int(
        binding_evidence.stored_identity_payload_size_bytes,
        field="P78 stored identity payload size",
    )
    identity_binding = _sha256(
        binding_evidence.receipt_identity_binding_sha256,
        field="P78 receipt identity binding SHA-256",
    )

    payload = {
        "admission_binding_sha256": admission_binding,
        "lineage_sha256": lineage,
        "p78_evidence_state": P78_EVIDENCE_STATE,
        "receipt_identity_binding_sha256": identity_binding,
        "receipt_payload_sha256": receipt_sha,
        "receipt_payload_size_bytes": receipt_size,
        "sequence": sequence,
        "stored_identity_payload_sha256": stored_sha,
        "stored_identity_payload_size_bytes": stored_size,
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()

    decoded = json.loads(encoded.decode("utf-8"))
    if decoded != payload:
        raise ValueError("canonical P78 binding receipt readback mismatch")

    return RecoveryStartupStoredReceiptBindingReceiptEvidence(
        sequence=sequence,
        lineage_sha256=lineage,
        receipt_payload_sha256=receipt_sha,
        receipt_payload_size_bytes=receipt_size,
        admission_binding_sha256=admission_binding,
        stored_identity_payload_sha256=stored_sha,
        stored_identity_payload_size_bytes=stored_size,
        receipt_identity_binding_sha256=identity_binding,
        binding_receipt_payload_sha256=digest,
        binding_receipt_payload_size_bytes=len(encoded),
        binding_receipt_payload_utf8=encoded,
        canonical_receipt_verified=True,
        exact_payload_identity_verified=True,
        p78_evidence_state=binding_evidence.evidence_state,
    )
