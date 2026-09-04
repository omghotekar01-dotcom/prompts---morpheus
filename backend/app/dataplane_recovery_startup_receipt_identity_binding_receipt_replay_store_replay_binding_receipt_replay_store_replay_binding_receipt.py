"""Canonicalize verified P88 replay/retained-identity composition evidence.

P89 is the serialization boundary for the P88 read-only composition result. It
validates the complete P88 contract, emits strict canonical JSON bytes, and
reports the exact byte length and SHA-256 identity of those bytes.

This is portability evidence only. Canonical bytes do not authenticate their
source, establish freshness or monotonicity, persist a trusted head, prevent
rollback/replay, or authorize startup or mutation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding import (
    EVIDENCE_STATE as P88_EVIDENCE_STATE,
    RecoveryStartupReplayStoredIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence,
)

EVIDENCE_STATE = (
    "LOCAL_DATA_PLANE_RECOVERY_STARTUP_ADMISSION_STORED_RECEIPT_BINDING_RECEIPT_REPLAY_STORED_IDENTITY_BINDING_"
    "RECEIPT_REPLAY_IDENTITY_STORED_REPLAY_BINDING_RECEIPT_CANONICAL"
)
SCHEMA = "morpheus.recovery.p89.replay-retained-identity-binding-receipt.v1"
TRUTH_BOUNDARY = (
    "This read-only portability gate proves only that a compatible supplied P88 evidence object satisfied its exported verification "
    "contract and was serialized into deterministic canonical JSON bytes whose exact byte length and SHA-256 are reported. It does not "
    "authenticate P88 or the receipt bytes, rerun P85/P87/P88 or dependencies, establish freshness/latest/global/monotonic head truth, "
    "prevent replay or coordinated rollback, retain a trusted head, authorize startup or mutation, provide CAS, leases, fencing, TPM/HSM "
    "protection, remote witnessing, distributed consensus, HA, production readiness, benchmark evidence, novelty evidence, or automatic-control authority."
)

_P88_FLAGS = (
    "p85_contract_verified",
    "p87_contract_verified",
    "cross_evidence_identity_verified",
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
class RecoveryStartupReplayRetainedIdentityBindingReceiptEvidence:
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
    payload: bytes
    payload_sha256: str
    payload_size_bytes: int
    p88_contract_verified: bool
    canonical_receipt_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "lineage_sha256": self.lineage_sha256,
            "binding_receipt_payload_sha256": self.binding_receipt_payload_sha256,
            "binding_receipt_payload_size_bytes": self.binding_receipt_payload_size_bytes,
            "receipt_identity_binding_sha256": self.receipt_identity_binding_sha256,
            "retained_identity_payload_sha256": self.retained_identity_payload_sha256,
            "retained_identity_payload_size_bytes": self.retained_identity_payload_size_bytes,
            "replay_stored_identity_binding_sha256": self.replay_stored_identity_binding_sha256,
            "replay_binding_receipt_payload_sha256": self.replay_binding_receipt_payload_sha256,
            "replay_binding_receipt_payload_size_bytes": self.replay_binding_receipt_payload_size_bytes,
            "retained_replay_identity_payload_sha256": self.retained_replay_identity_payload_sha256,
            "retained_replay_identity_payload_size_bytes": self.retained_replay_identity_payload_size_bytes,
            "replay_retained_identity_binding_sha256": self.replay_retained_identity_binding_sha256,
            "payload_sha256": self.payload_sha256,
            "payload_size_bytes": self.payload_size_bytes,
            "p88_contract_verified": self.p88_contract_verified,
            "canonical_receipt_verified": self.canonical_receipt_verified,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def canonicalize_recovery_startup_replay_retained_identity_binding_receipt(
    evidence: RecoveryStartupReplayStoredIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence,
) -> RecoveryStartupReplayRetainedIdentityBindingReceiptEvidence:
    """Serialize P88 evidence canonically without granting startup authority."""
    if not isinstance(evidence, RecoveryStartupReplayStoredIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence):
        raise ValueError("P88 replay/retained-identity binding evidence has an incompatible type")
    if evidence.evidence_state != P88_EVIDENCE_STATE:
        raise ValueError("P88 replay/retained-identity binding evidence state is incompatible")
    if evidence.automatic_control_allowed is not False:
        raise ValueError("P88 evidence must not grant automatic-control authority")
    for field in _P88_FLAGS:
        if getattr(evidence, field, None) is not True:
            raise ValueError(f"P88 {field} verification is incomplete")

    sequence = _positive_int(evidence.sequence, field="P88 sequence")
    lineage = _sha256(evidence.lineage_sha256, field="P88 lineage SHA-256")
    binding_receipt_sha = _sha256(evidence.binding_receipt_payload_sha256, field="P88 binding receipt payload SHA-256")
    binding_receipt_size = _positive_int(evidence.binding_receipt_payload_size_bytes, field="P88 binding receipt payload size")
    receipt_identity_binding = _sha256(evidence.receipt_identity_binding_sha256, field="P88 receipt identity binding SHA-256")
    retained_identity_sha = _sha256(evidence.retained_identity_payload_sha256, field="P88 retained identity payload SHA-256")
    retained_identity_size = _positive_int(evidence.retained_identity_payload_size_bytes, field="P88 retained identity payload size")
    replay_stored_binding = _sha256(evidence.replay_stored_identity_binding_sha256, field="P88 replay/stored-identity binding SHA-256")
    replay_receipt_sha = _sha256(evidence.replay_binding_receipt_payload_sha256, field="P88 replay binding receipt payload SHA-256")
    replay_receipt_size = _positive_int(evidence.replay_binding_receipt_payload_size_bytes, field="P88 replay binding receipt payload size")
    retained_replay_sha = _sha256(evidence.retained_replay_identity_payload_sha256, field="P88 retained replay identity payload SHA-256")
    retained_replay_size = _positive_int(evidence.retained_replay_identity_payload_size_bytes, field="P88 retained replay identity payload size")
    composition_binding = _sha256(evidence.replay_retained_identity_binding_sha256, field="P88 replay/retained-identity binding SHA-256")

    document = {
        "schema": SCHEMA,
        "sequence": sequence,
        "lineage_sha256": lineage,
        "binding_receipt_payload_sha256": binding_receipt_sha,
        "binding_receipt_payload_size_bytes": binding_receipt_size,
        "receipt_identity_binding_sha256": receipt_identity_binding,
        "retained_identity_payload_sha256": retained_identity_sha,
        "retained_identity_payload_size_bytes": retained_identity_size,
        "replay_stored_identity_binding_sha256": replay_stored_binding,
        "replay_binding_receipt_payload_sha256": replay_receipt_sha,
        "replay_binding_receipt_payload_size_bytes": replay_receipt_size,
        "retained_replay_identity_payload_sha256": retained_replay_sha,
        "retained_replay_identity_payload_size_bytes": retained_replay_size,
        "replay_retained_identity_binding_sha256": composition_binding,
        "p88_evidence_state": P88_EVIDENCE_STATE,
    }
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    canonical_readback = json.dumps(
        json.loads(payload.decode("utf-8")),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    if canonical_readback != payload:
        raise RuntimeError("canonical P89 receipt readback mismatch")

    return RecoveryStartupReplayRetainedIdentityBindingReceiptEvidence(
        sequence=sequence,
        lineage_sha256=lineage,
        binding_receipt_payload_sha256=binding_receipt_sha,
        binding_receipt_payload_size_bytes=binding_receipt_size,
        receipt_identity_binding_sha256=receipt_identity_binding,
        retained_identity_payload_sha256=retained_identity_sha,
        retained_identity_payload_size_bytes=retained_identity_size,
        replay_stored_identity_binding_sha256=replay_stored_binding,
        replay_binding_receipt_payload_sha256=replay_receipt_sha,
        replay_binding_receipt_payload_size_bytes=replay_receipt_size,
        retained_replay_identity_payload_sha256=retained_replay_sha,
        retained_replay_identity_payload_size_bytes=retained_replay_size,
        replay_retained_identity_binding_sha256=composition_binding,
        payload=payload,
        payload_sha256=hashlib.sha256(payload).hexdigest(),
        payload_size_bytes=len(payload),
        p88_contract_verified=True,
        canonical_receipt_verified=True,
    )
