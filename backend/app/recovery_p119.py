"""Canonicalize verified P118 P115/P117 replay-composition evidence.

P119 is a portability gate only: it validates P118's exported consistency contract,
serializes the verified identity as strict canonical JSON, and reports exact bytes,
SHA-256, and byte length. It grants no startup or mutation authority.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .recovery_p118 import (
    EVIDENCE_STATE as P118_EVIDENCE_STATE,
    _FIELDS as P118_SHARED_FIELDS,
    RecoveryP115P117CompositionEvidence,
)

EVIDENCE_STATE = P118_EVIDENCE_STATE + "_RECEIPT_CANONICAL"
SCHEMA = "morpheus.recovery.p119.p115-p117-replay-composition-binding-receipt.v1"
TRUTH_BOUNDARY = (
    "This read-only portability gate proves only that a compatible supplied P118 evidence object satisfied its exported verification "
    "contract and was serialized into deterministic canonical JSON bytes whose exact byte length and SHA-256 are reported. It does not "
    "authenticate P118 or the receipt bytes, rerun P115/P117/P118 or dependencies, establish freshness/latest/global/monotonic head truth, "
    "prevent replay or coordinated rollback, retain a trusted head, authorize startup or mutation, provide CAS, leases, fencing, TPM/HSM "
    "protection, remote witnessing, distributed consensus, HA, production readiness, benchmark evidence, novelty evidence, or automatic-control authority."
)
_P118_FLAGS = ("p115_contract_verified", "p117_contract_verified", "cross_evidence_identity_verified")
_FIELDS = P118_SHARED_FIELDS + (
    ("retained_p116_record_payload_sha256", "sha"),
    ("retained_p116_record_payload_size_bytes", "int"),
    ("p115_p117_composition_binding_sha256", "sha"),
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
class RecoveryP118CompositionReceiptEvidence:
    payload: bytes
    payload_sha256: str
    payload_size_bytes: int
    p118_contract_verified: bool
    canonical_receipt_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "payload_sha256": self.payload_sha256,
            "payload_size_bytes": self.payload_size_bytes,
            "p118_contract_verified": self.p118_contract_verified,
            "canonical_receipt_verified": self.canonical_receipt_verified,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def canonicalize_p118_composition_receipt(evidence: RecoveryP115P117CompositionEvidence) -> RecoveryP118CompositionReceiptEvidence:
    """Serialize compatible P118 consistency evidence into strict canonical bytes."""
    if not isinstance(evidence, RecoveryP115P117CompositionEvidence):
        raise ValueError("P118 P115/P117 replay composition evidence has an incompatible type")
    if evidence.evidence_state != P118_EVIDENCE_STATE:
        raise ValueError("P118 evidence state is incompatible")
    if evidence.automatic_control_allowed is not False:
        raise ValueError("P118 evidence must not grant automatic-control authority")
    if any(getattr(evidence, flag, None) is not True for flag in _P118_FLAGS):
        raise ValueError("P118 verification flags are incomplete")

    values: dict[str, object] = {}
    for field, kind in _FIELDS:
        raw = getattr(evidence, field, None)
        values[field] = _positive_int(raw, field=f"P118 {field}") if kind == "int" else _sha256(raw, field=f"P118 {field}")

    document = {"schema": SCHEMA, **values, "p118_evidence_state": P118_EVIDENCE_STATE}
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return RecoveryP118CompositionReceiptEvidence(
        payload=payload,
        payload_sha256=hashlib.sha256(payload).hexdigest(),
        payload_size_bytes=len(payload),
        p118_contract_verified=True,
        canonical_receipt_verified=True,
    )
