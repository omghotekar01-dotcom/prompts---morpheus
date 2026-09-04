"""Independently verify canonical P74 startup-admission receipt bytes.

P75 closes the consumer-side portability seam left by P74. P74 emits canonical
receipt bytes and their identity; P75 accepts receipt bytes plus an independently
supplied expected byte identity, validates strict canonical encoding and the
declared dependency states, then recomputes the P73 admission binding from the
receipt semantics.

This remains replay/consistency evidence. It does not authenticate where the
expected identity came from, prove freshness, retain the receipt, or authorize
startup or mutation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .dataplane_recovery_anchor_rebootstrap import EVIDENCE_STATE as P67_EVIDENCE_STATE
from .dataplane_recovery_anchor_repeat_observation import (
    EVIDENCE_STATE as P72_EVIDENCE_STATE,
)

EVIDENCE_STATE = "LOCAL_DATA_PLANE_RECOVERY_STARTUP_ADMISSION_RECEIPT_REPLAY_VERIFIED"
TRUTH_BOUNDARY = (
    "This gate proves only that supplied P74-format receipt bytes match a supplied expected byte identity, are strict canonical "
    "JSON with the exact supported schema, carry the expected P67/P72 evidence states, and contain a P73 admission binding that "
    "recomputes from those receipt semantics. It does not authenticate or independently retain the expected identity or receipt, "
    "prove freshness or latest/global/monotonic head truth, prevent rollback or replay of an older internally valid receipt, "
    "rerun P67/P72/P73/P74, authorize startup or mutation, provide atomicity, CAS, leases, fencing, TPM/HSM protection, remote "
    "witnessing, distributed consensus, HA, native-object recovery, cross-process hot swap, production readiness, benchmark "
    "evidence, novelty evidence, or automatic-control authority."
)

_REQUIRED_KEYS = frozenset(
    {
        "admission_binding_sha256",
        "lineage_sha256",
        "observed_anchor_payload_sha256",
        "observed_anchor_payload_size_bytes",
        "p67_binding_sha256",
        "p67_evidence_state",
        "p72_evidence_state",
        "sequence",
    }
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
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class RecoveryStartupAdmissionReceiptReplayEvidence:
    sequence: int
    lineage_sha256: str
    admission_binding_sha256: str
    receipt_payload_sha256: str
    receipt_payload_size_bytes: int
    expected_payload_identity_verified: bool
    canonical_receipt_verified: bool
    admission_binding_recomputed_verified: bool
    dependency_states_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def verify_recovery_startup_admission_receipt(
    receipt_payload_utf8: bytes,
    *,
    expected_payload_sha256: str,
    expected_payload_size_bytes: int,
) -> RecoveryStartupAdmissionReceiptReplayEvidence:
    """Strictly verify one P74-format canonical receipt against an expected byte identity."""
    if not isinstance(receipt_payload_utf8, bytes):
        raise ValueError("startup-admission receipt payload must be bytes")

    expected_sha = _sha256(
        expected_payload_sha256, field="expected receipt payload SHA-256"
    )
    expected_size = _positive_int(
        expected_payload_size_bytes, field="expected receipt payload size"
    )
    if len(receipt_payload_utf8) != expected_size:
        raise ValueError("startup-admission receipt payload size does not match expected identity")
    actual_sha = hashlib.sha256(receipt_payload_utf8).hexdigest()
    if actual_sha != expected_sha:
        raise ValueError("startup-admission receipt payload SHA-256 does not match expected identity")

    try:
        text = receipt_payload_utf8.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("startup-admission receipt payload must be valid UTF-8") from exc
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError("startup-admission receipt payload must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("startup-admission receipt payload must be a JSON object")
    if set(payload) != _REQUIRED_KEYS:
        raise ValueError("startup-admission receipt payload has an unsupported schema")

    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    if canonical != receipt_payload_utf8:
        raise ValueError("startup-admission receipt payload is not strict canonical JSON")

    sequence = _positive_int(payload["sequence"], field="receipt sequence")
    lineage = _sha256(payload["lineage_sha256"], field="receipt lineage SHA-256")
    p67_binding = _sha256(
        payload["p67_binding_sha256"], field="receipt P67 binding SHA-256"
    )
    observed_sha = _sha256(
        payload["observed_anchor_payload_sha256"],
        field="receipt observed anchor payload SHA-256",
    )
    observed_size = _positive_int(
        payload["observed_anchor_payload_size_bytes"],
        field="receipt observed anchor payload size",
    )
    admission_binding = _sha256(
        payload["admission_binding_sha256"],
        field="receipt admission binding SHA-256",
    )
    if payload["p67_evidence_state"] != P67_EVIDENCE_STATE:
        raise ValueError("receipt P67 evidence state is incompatible")
    if payload["p72_evidence_state"] != P72_EVIDENCE_STATE:
        raise ValueError("receipt P72 evidence state is incompatible")

    binding_payload = {
        "sequence": sequence,
        "lineage_sha256": lineage,
        "p67_binding_sha256": p67_binding,
        "observed_anchor_payload_sha256": observed_sha,
        "observed_anchor_payload_size_bytes": observed_size,
        "p67_evidence_state": payload["p67_evidence_state"],
        "p72_evidence_state": payload["p72_evidence_state"],
    }
    recomputed_binding = _canonical_sha(binding_payload)
    if recomputed_binding != admission_binding:
        raise ValueError("receipt P73 admission binding does not recompute")

    return RecoveryStartupAdmissionReceiptReplayEvidence(
        sequence=sequence,
        lineage_sha256=lineage,
        admission_binding_sha256=admission_binding,
        receipt_payload_sha256=actual_sha,
        receipt_payload_size_bytes=len(receipt_payload_utf8),
        expected_payload_identity_verified=True,
        canonical_receipt_verified=True,
        admission_binding_recomputed_verified=True,
        dependency_states_verified=True,
    )
