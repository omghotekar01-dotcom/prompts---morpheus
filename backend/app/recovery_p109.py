"""Canonicalize verified P108 P105/P107 replay-composition evidence.

P109 is a portability gate only: it validates P108's exported consistency contract,
serializes the verified identity as strict canonical JSON, and reports exact bytes,
SHA-256, and byte length. It grants no startup or mutation authority.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .recovery_p108 import (
    EVIDENCE_STATE as P108_EVIDENCE_STATE,
    _FIELDS as P108_SHARED_FIELDS,
    RecoveryP105P107CompositionEvidence,
)

EVIDENCE_STATE = P108_EVIDENCE_STATE + "_RECEIPT_CANONICAL"
SCHEMA = "morpheus.recovery.p109.p105-p107-replay-composition-binding-receipt.v1"
TRUTH_BOUNDARY = (
    "This read-only portability gate proves only that a compatible supplied P108 evidence object satisfied its exported verification "
    "contract and was serialized into deterministic canonical JSON bytes whose exact byte length and SHA-256 are reported. It does not "
    "authenticate P108 or the receipt bytes, rerun P105/P107/P108 or dependencies, establish freshness/latest/global/monotonic head truth, "
    "prevent replay or coordinated rollback, retain a trusted head, authorize startup or mutation, provide CAS, leases, fencing, TPM/HSM "
    "protection, remote witnessing, distributed consensus, HA, production readiness, benchmark evidence, novelty evidence, or automatic-control authority."
)
_P108_FLAGS = ("p105_contract_verified", "p107_contract_verified", "cross_evidence_identity_verified")
_FIELDS = P108_SHARED_FIELDS + (
    ("retained_p106_record_payload_sha256", "sha"),
    ("retained_p106_record_payload_size_bytes", "int"),
    ("p105_p107_composition_binding_sha256", "sha"),
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
class RecoveryP108CompositionReceiptEvidence:
    payload: bytes
    payload_sha256: str
    payload_size_bytes: int
    p108_contract_verified: bool
    canonical_receipt_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "payload_sha256": self.payload_sha256,
            "payload_size_bytes": self.payload_size_bytes,
            "p108_contract_verified": self.p108_contract_verified,
            "canonical_receipt_verified": self.canonical_receipt_verified,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def canonicalize_p108_composition_receipt(evidence: RecoveryP105P107CompositionEvidence) -> RecoveryP108CompositionReceiptEvidence:
    if not isinstance(evidence, RecoveryP105P107CompositionEvidence):
        raise ValueError("P108 P105/P107 replay composition evidence has an incompatible type")
    if evidence.evidence_state != P108_EVIDENCE_STATE:
        raise ValueError("P108 evidence state is incompatible")
    if evidence.automatic_control_allowed is not False:
        raise ValueError("P108 evidence must not grant automatic-control authority")
    if any(getattr(evidence, flag, None) is not True for flag in _P108_FLAGS):
        raise ValueError("P108 verification flags are incomplete")

    values: dict[str, object] = {}
    for field, kind in _FIELDS:
        raw = getattr(evidence, field, None)
        values[field] = _positive_int(raw, field=f"P108 {field}") if kind == "int" else _sha256(raw, field=f"P108 {field}")

    document = {"schema": SCHEMA, **values, "p108_evidence_state": P108_EVIDENCE_STATE}
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return RecoveryP108CompositionReceiptEvidence(
        payload=payload,
        payload_sha256=hashlib.sha256(payload).hexdigest(),
        payload_size_bytes=len(payload),
        p108_contract_verified=True,
        canonical_receipt_verified=True,
    )
