"""Canonicalize verified P103 P100/P102 replay-composition evidence.

P104 is the portability boundary for the P103 read-only composition result. It
validates the full P103 contract, emits strict canonical JSON bytes, and reports
the exact byte length and SHA-256 identity of those bytes.

This is portability evidence only. Canonical bytes do not authenticate their
source, establish freshness or monotonicity, persist a trusted head, prevent
rollback/replay, or authorize startup or mutation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .recovery_p103 import (
    EVIDENCE_STATE as P103_EVIDENCE_STATE,
    RecoveryP100P102CompositionEvidence,
)

EVIDENCE_STATE = (
    "LOCAL_DATA_PLANE_RECOVERY_STARTUP_ADMISSION_STORED_RECEIPT_BINDING_RECEIPT_REPLAY_STORED_IDENTITY_BINDING_"
    "RECEIPT_REPLAY_IDENTITY_STORED_REPLAY_BINDING_RECEIPT_REPLAY_VERIFIED_IDENTITY_STORED_REPLAY_BINDING_RECEIPT_REPLAY_"
    "VERIFIED_IDENTITY_STORED_REPLAY_BINDING_VERIFIED_RECEIPT_REPLAY_VERIFIED_IDENTITY_STORED_VERIFIED_BINDING_VERIFIED_"
    "RECEIPT_CANONICAL"
)
SCHEMA = "morpheus.recovery.p104.p100-p102-replay-composition-binding-receipt.v1"
TRUTH_BOUNDARY = (
    "This read-only portability gate proves only that a compatible supplied P103 evidence object satisfied its exported verification "
    "contract and was serialized into deterministic canonical JSON bytes whose exact byte length and SHA-256 are reported. It does not "
    "authenticate P103 or the receipt bytes, rerun P100/P102/P103 or dependencies, establish freshness/latest/global/monotonic head truth, "
    "prevent replay or coordinated rollback, retain a trusted head, authorize startup or mutation, provide CAS, leases, fencing, TPM/HSM "
    "protection, remote witnessing, distributed consensus, HA, native-object recovery, cross-process hot swap, production readiness, "
    "benchmark evidence, novelty evidence, or automatic-control authority."
)

_P103_FLAGS = ("p100_contract_verified", "p102_contract_verified", "cross_evidence_identity_verified")
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
    ("retained_replayed_receipt_identity_payload_sha256", "sha"),
    ("retained_replayed_receipt_identity_payload_size_bytes", "int"),
    ("replayed_receipt_retained_identity_binding_sha256", "sha"),
    ("replayed_receipt_retained_identity_binding_receipt_payload_sha256", "sha"),
    ("replayed_receipt_retained_identity_binding_receipt_payload_size_bytes", "int"),
    ("retained_p101_record_payload_sha256", "sha"),
    ("retained_p101_record_payload_size_bytes", "int"),
    ("p100_p102_composition_binding_sha256", "sha"),
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


@dataclass(frozen=True)
class RecoveryP103CompositionReceiptEvidence:
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
    replayed_receipt_retained_identity_binding_receipt_payload_sha256: str
    replayed_receipt_retained_identity_binding_receipt_payload_size_bytes: int
    retained_p101_record_payload_sha256: str
    retained_p101_record_payload_size_bytes: int
    p100_p102_composition_binding_sha256: str
    payload: bytes
    payload_sha256: str
    payload_size_bytes: int
    p103_contract_verified: bool
    canonical_receipt_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        data = {key: value for key, value in self.__dict__.items() if key != "payload"}
        return {**data, "truth_boundary": TRUTH_BOUNDARY}


def canonicalize_p103_composition_receipt(
    evidence: RecoveryP100P102CompositionEvidence,
) -> RecoveryP103CompositionReceiptEvidence:
    """Serialize P103 composition evidence canonically without granting authority."""
    if not isinstance(evidence, RecoveryP100P102CompositionEvidence):
        raise ValueError("P103 P100/P102 replay composition evidence has an incompatible type")
    if evidence.evidence_state != P103_EVIDENCE_STATE:
        raise ValueError("P103 evidence state is incompatible")
    if evidence.automatic_control_allowed is not False:
        raise ValueError("P103 evidence must not grant automatic-control authority")
    if any(getattr(evidence, flag, None) is not True for flag in _P103_FLAGS):
        raise ValueError("P103 verification flags are incomplete")

    values: dict[str, object] = {}
    for field, kind in _FIELDS:
        raw = getattr(evidence, field, None)
        values[field] = (
            _positive_int(raw, field=f"P103 {field}")
            if kind == "int"
            else _sha256(raw, field=f"P103 {field}")
        )

    document = {"schema": SCHEMA, **values, "p103_evidence_state": P103_EVIDENCE_STATE}
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()

    return RecoveryP103CompositionReceiptEvidence(
        **values,
        payload=payload,
        payload_sha256=digest,
        payload_size_bytes=len(payload),
        p103_contract_verified=True,
        canonical_receipt_verified=True,
    )
