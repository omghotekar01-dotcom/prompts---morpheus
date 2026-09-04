"""Replay and independently verify a canonical P79 stored-receipt binding receipt.

P80 is the consumer-side counterpart to P79. A caller supplies the exact P79
receipt bytes together with an expected byte length and SHA-256. This gate
verifies that byte identity, requires strict canonical JSON and the exact P79
schema, validates the embedded dependency-state contract, and independently
recomputes the P78 receipt/stored-identity binding from the serialized semantic
identities instead of trusting the serialized binding field.

This is read-only replay consistency evidence. It does not authenticate the
expected identity, establish freshness or monotonicity, or authorize startup or
mutation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .dataplane_recovery_startup_receipt_identity_binding import (
    EVIDENCE_STATE as P78_EVIDENCE_STATE,
)
from .dataplane_recovery_startup_receipt_identity_replay import (
    EVIDENCE_STATE as P77_EVIDENCE_STATE,
)
from .dataplane_recovery_startup_receipt_replay import (
    EVIDENCE_STATE as P75_EVIDENCE_STATE,
)

EVIDENCE_STATE = (
    "LOCAL_DATA_PLANE_RECOVERY_STARTUP_ADMISSION_STORED_RECEIPT_BINDING_RECEIPT_REPLAY_VERIFIED"
)
TRUTH_BOUNDARY = (
    "This read-only gate proves only that supplied P79 binding-receipt bytes matched a caller-supplied expected SHA-256 and byte "
    "length, were exact canonical JSON with the supported schema and P78 evidence-state identity, and contained a P78 "
    "receipt/stored-identity binding that recomputed from the serialized semantic identities during this call. It does not authenticate "
    "the expected byte identity or its source, establish freshness/latest/global/monotonic head truth, prevent replay or coordinated "
    "rollback, rerun P79/P78/P75/P77 or their dependencies, persist or independently retain evidence, provide atomicity after return, "
    "authorize startup or mutation, provide CAS, leases, fencing, TPM/HSM protection, remote witnessing, distributed consensus, HA, "
    "native-object recovery, cross-process hot swap, production readiness, benchmark evidence, novelty evidence, or automatic-control "
    "authority."
)

_EXPECTED_KEYS = {
    "admission_binding_sha256",
    "lineage_sha256",
    "p78_evidence_state",
    "receipt_identity_binding_sha256",
    "receipt_payload_sha256",
    "receipt_payload_size_bytes",
    "sequence",
    "stored_identity_payload_sha256",
    "stored_identity_payload_size_bytes",
}


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
class RecoveryStartupStoredReceiptBindingReceiptReplayEvidence:
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
    expected_payload_identity_verified: bool
    canonical_receipt_verified: bool
    dependency_state_verified: bool
    receipt_identity_binding_recomputed_verified: bool
    p78_evidence_state: str
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def replay_recovery_startup_stored_receipt_binding_receipt(
    payload_utf8: bytes,
    *,
    expected_payload_sha256: str,
    expected_payload_size_bytes: int,
) -> RecoveryStartupStoredReceiptBindingReceiptReplayEvidence:
    """Verify exact P79 receipt bytes and independently recompute the P78 binding."""
    if not isinstance(payload_utf8, bytes):
        raise ValueError("P79 binding receipt payload must be bytes")

    expected_sha = _sha256(
        expected_payload_sha256, field="expected P79 binding receipt payload SHA-256"
    )
    expected_size = _positive_int(
        expected_payload_size_bytes, field="expected P79 binding receipt payload size"
    )

    if len(payload_utf8) != expected_size:
        raise ValueError("P79 binding receipt payload byte length mismatch")
    observed_sha = hashlib.sha256(payload_utf8).hexdigest()
    if observed_sha != expected_sha:
        raise ValueError("P79 binding receipt payload SHA-256 mismatch")

    try:
        text = payload_utf8.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("P79 binding receipt payload is not valid UTF-8") from exc

    try:
        decoded = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("P79 binding receipt payload is not valid JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError("P79 binding receipt payload must decode to a JSON object")
    if set(decoded) != _EXPECTED_KEYS:
        raise ValueError("P79 binding receipt payload schema is incompatible")

    canonical = json.dumps(
        decoded, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    if canonical != payload_utf8:
        raise ValueError("P79 binding receipt payload is not strict canonical JSON")

    p78_state = decoded["p78_evidence_state"]
    if p78_state != P78_EVIDENCE_STATE:
        raise ValueError("P79 binding receipt P78 evidence state is incompatible")

    sequence = _positive_int(decoded["sequence"], field="P79 sequence")
    lineage = _sha256(decoded["lineage_sha256"], field="P79 lineage SHA-256")
    receipt_sha = _sha256(
        decoded["receipt_payload_sha256"], field="P79 receipt payload SHA-256"
    )
    receipt_size = _positive_int(
        decoded["receipt_payload_size_bytes"], field="P79 receipt payload size"
    )
    admission_binding = _sha256(
        decoded["admission_binding_sha256"], field="P79 admission binding SHA-256"
    )
    stored_sha = _sha256(
        decoded["stored_identity_payload_sha256"],
        field="P79 stored identity payload SHA-256",
    )
    stored_size = _positive_int(
        decoded["stored_identity_payload_size_bytes"],
        field="P79 stored identity payload size",
    )
    serialized_binding = _sha256(
        decoded["receipt_identity_binding_sha256"],
        field="P79 receipt identity binding SHA-256",
    )

    recomputed_binding = _canonical_sha(
        {
            "sequence": sequence,
            "lineage_sha256": lineage,
            "receipt_payload_sha256": receipt_sha,
            "receipt_payload_size_bytes": receipt_size,
            "admission_binding_sha256": admission_binding,
            "stored_identity_payload_sha256": stored_sha,
            "stored_identity_payload_size_bytes": stored_size,
            "p75_evidence_state": P75_EVIDENCE_STATE,
            "p77_evidence_state": P77_EVIDENCE_STATE,
        }
    )
    if recomputed_binding != serialized_binding:
        raise ValueError("P79 receipt identity binding recomputation mismatch")

    return RecoveryStartupStoredReceiptBindingReceiptReplayEvidence(
        sequence=sequence,
        lineage_sha256=lineage,
        receipt_payload_sha256=receipt_sha,
        receipt_payload_size_bytes=receipt_size,
        admission_binding_sha256=admission_binding,
        stored_identity_payload_sha256=stored_sha,
        stored_identity_payload_size_bytes=stored_size,
        receipt_identity_binding_sha256=serialized_binding,
        binding_receipt_payload_sha256=observed_sha,
        binding_receipt_payload_size_bytes=len(payload_utf8),
        expected_payload_identity_verified=True,
        canonical_receipt_verified=True,
        dependency_state_verified=True,
        receipt_identity_binding_recomputed_verified=True,
        p78_evidence_state=p78_state,
    )
