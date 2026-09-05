"""Canonicalize verified P98 P95/P97 replay-composition evidence.

P99 is the serialization boundary for the P98 read-only composition result. It
validates the complete P98 contract, emits strict canonical JSON bytes, and
reports the exact byte length and SHA-256 identity of those bytes.

This is portability evidence only. Canonical bytes do not authenticate their
source, establish freshness or monotonicity, persist a trusted head, prevent
rollback/replay, or authorize startup or mutation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding import (
    EVIDENCE_STATE as P98_EVIDENCE_STATE,
    RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence,
)

EVIDENCE_STATE = (
    "LOCAL_DATA_PLANE_RECOVERY_STARTUP_ADMISSION_STORED_RECEIPT_BINDING_RECEIPT_REPLAY_STORED_IDENTITY_BINDING_"
    "RECEIPT_REPLAY_IDENTITY_STORED_REPLAY_BINDING_RECEIPT_REPLAY_VERIFIED_IDENTITY_STORED_REPLAY_BINDING_RECEIPT_REPLAY_"
    "VERIFIED_IDENTITY_STORED_REPLAY_BINDING_VERIFIED_RECEIPT_CANONICAL"
)
SCHEMA = "morpheus.recovery.p99.p95-p97-replay-composition-binding-receipt.v1"
TRUTH_BOUNDARY = (
    "This read-only portability gate proves only that a compatible supplied P98 evidence object satisfied its exported verification contract "
    "and was serialized into deterministic canonical JSON bytes whose exact byte length and SHA-256 are reported. It does not authenticate P98 "
    "or the receipt bytes, rerun P95/P97/P98 or dependencies, establish freshness/latest/global/monotonic head truth, prevent replay or coordinated "
    "rollback, retain a trusted head, authorize startup or mutation, provide CAS, leases, fencing, TPM/HSM protection, remote witnessing, distributed "
    "consensus, HA, production readiness, benchmark evidence, novelty evidence, or automatic-control authority."
)

_P98_FLAGS = ("p95_contract_verified", "p97_contract_verified", "cross_evidence_identity_verified")
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
class RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingReceiptEvidence:
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
    payload: bytes
    payload_sha256: str
    payload_size_bytes: int
    p98_contract_verified: bool
    canonical_receipt_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        data = {k: v for k, v in self.__dict__.items() if k != "payload"}
        return {**data, "truth_boundary": TRUTH_BOUNDARY}


def canonicalize_recovery_startup_p95_p97_replay_composition_binding_receipt(
    evidence: RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence,
) -> RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingReceiptEvidence:
    """Serialize P98 composition evidence canonically without granting authority."""
    if not isinstance(evidence, RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence):
        raise ValueError("P98 P95/P97 replay composition evidence has an incompatible type")
    if evidence.evidence_state != P98_EVIDENCE_STATE:
        raise ValueError("P98 evidence state is incompatible")
    if evidence.automatic_control_allowed is not False:
        raise ValueError("P98 evidence must not grant automatic-control authority")
    if any(getattr(evidence, flag, None) is not True for flag in _P98_FLAGS):
        raise ValueError("P98 verification flags are incomplete")

    values: dict[str, object] = {}
    for field, kind in _FIELDS:
        raw = getattr(evidence, field, None)
        values[field] = _positive_int(raw, field=f"P98 {field}") if kind == "int" else _sha256(raw, field=f"P98 {field}")

    document = {"schema": SCHEMA, **values, "p98_evidence_state": P98_EVIDENCE_STATE}
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingReceiptEvidence(
        **values,
        payload=payload,
        payload_sha256=digest,
        payload_size_bytes=len(payload),
        p98_contract_verified=True,
        canonical_receipt_verified=True,
    )
