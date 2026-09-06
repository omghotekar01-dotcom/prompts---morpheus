"""Canonicalize verified P123 P120/P122 replay-composition evidence.

P124 is a portability gate only: it validates P123's exported consistency contract,
serializes the verified identity as strict canonical JSON, and reports exact bytes,
SHA-256, and byte length. It grants no startup or mutation authority.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .recovery_p123 import (
    EVIDENCE_STATE as P123_EVIDENCE_STATE,
    _FIELDS as P123_SHARED_FIELDS,
    RecoveryP120P122CompositionEvidence,
)

EVIDENCE_STATE = P123_EVIDENCE_STATE + "_RECEIPT_CANONICAL"
SCHEMA = "morpheus.recovery.p124.p120-p122-replay-composition-binding-receipt.v1"
TRUTH_BOUNDARY = (
    "This read-only portability gate proves only that a compatible supplied P123 evidence object satisfied its exported verification "
    "contract and was serialized into deterministic canonical JSON bytes whose exact byte length and SHA-256 are reported. It does not "
    "authenticate P123 or the receipt bytes, rerun P120/P122/P123 or dependencies, establish freshness/latest/global/monotonic head truth, "
    "prevent replay or coordinated rollback, retain a trusted head, authorize startup or mutation, provide CAS, leases, fencing, TPM/HSM "
    "protection, remote witnessing, distributed consensus, HA, production readiness, benchmark evidence, novelty evidence, or automatic-control authority."
)
_P123_FLAGS = ("p120_contract_verified", "p122_contract_verified", "cross_evidence_identity_verified")
_FIELDS = P123_SHARED_FIELDS + (
    ("retained_p121_record_payload_sha256", "sha"),
    ("retained_p121_record_payload_size_bytes", "int"),
    ("p120_p122_composition_binding_sha256", "sha"),
)


def _positive_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _sha256(value: object, *, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or value.lower() != value or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{field} must be 64 lowercase hexadecimal characters")
    return value


@dataclass(frozen=True)
class RecoveryP123CompositionReceiptEvidence:
    payload: bytes
    payload_sha256: str
    payload_size_bytes: int
    p123_contract_verified: bool
    canonical_receipt_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "payload_sha256": self.payload_sha256,
            "payload_size_bytes": self.payload_size_bytes,
            "p123_contract_verified": self.p123_contract_verified,
            "canonical_receipt_verified": self.canonical_receipt_verified,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def canonicalize_p123_composition_receipt(evidence: RecoveryP120P122CompositionEvidence) -> RecoveryP123CompositionReceiptEvidence:
    """Serialize compatible P123 consistency evidence into strict canonical bytes."""
    if not isinstance(evidence, RecoveryP120P122CompositionEvidence):
        raise ValueError("P123 P120/P122 replay composition evidence has an incompatible type")
    if evidence.evidence_state != P123_EVIDENCE_STATE:
        raise ValueError("P123 evidence state is incompatible")
    if evidence.automatic_control_allowed is not False:
        raise ValueError("P123 evidence must not grant automatic-control authority")
    if any(getattr(evidence, flag, None) is not True for flag in _P123_FLAGS):
        raise ValueError("P123 verification flags are incomplete")

    values: dict[str, object] = {}
    for field, kind in _FIELDS:
        raw = getattr(evidence, field, None)
        values[field] = _positive_int(raw, field=f"P123 {field}") if kind == "int" else _sha256(raw, field=f"P123 {field}")

    document = {"schema": SCHEMA, **values, "p123_evidence_state": P123_EVIDENCE_STATE}
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return RecoveryP123CompositionReceiptEvidence(
        payload=payload,
        payload_sha256=hashlib.sha256(payload).hexdigest(),
        payload_size_bytes=len(payload),
        p123_contract_verified=True,
        canonical_receipt_verified=True,
    )
