"""Replay and independently verify canonical P84 replay-composition receipt bytes.

P85 is the consumer-side counterpart to P84. A caller supplies exact P84 receipt
bytes with an expected byte length and SHA-256. This gate verifies that outer
byte identity, requires strict canonical JSON and the exact P84 schema, validates
the embedded P83 evidence-state contract, and independently recomputes the P83
P80/P82 replay-composition binding from serialized semantic identities rather
than trusting the serialized binding field.

This is read-only replay consistency evidence. It does not authenticate the
expected identity, establish freshness or monotonicity, or authorize startup or
mutation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay import (
    EVIDENCE_STATE as P80_EVIDENCE_STATE,
)
from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay import (
    EVIDENCE_STATE as P82_EVIDENCE_STATE,
)
from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding import (
    EVIDENCE_STATE as P83_EVIDENCE_STATE,
)
from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt import (
    SCHEMA as P84_SCHEMA,
)

EVIDENCE_STATE = "LOCAL_DATA_PLANE_RECOVERY_STARTUP_ADMISSION_STORED_RECEIPT_BINDING_RECEIPT_REPLAY_STORED_IDENTITY_BINDING_RECEIPT_REPLAY_VERIFIED"
TRUTH_BOUNDARY = (
    "This read-only gate proves only that supplied P84 receipt bytes matched a caller-supplied expected SHA-256 and byte length, were exact "
    "canonical JSON with the supported schema and P83 evidence-state identity, and contained a P83 P80/P82 replay-composition binding that "
    "recomputed from the serialized semantic identities during this call. It does not authenticate the expected byte identity or its source, "
    "establish freshness/latest/global/monotonic head truth, prevent replay or coordinated rollback, rerun P84/P83/P80/P82 or dependencies, "
    "persist or independently retain evidence, provide atomicity after return, authorize startup or mutation, provide CAS, leases, fencing, "
    "TPM/HSM protection, remote witnessing, distributed consensus, HA, native-object recovery, cross-process hot swap, production readiness, "
    "benchmark evidence, novelty evidence, or automatic-control authority."
)

_EXPECTED_KEYS = {
    "schema",
    "sequence",
    "lineage_sha256",
    "binding_receipt_payload_sha256",
    "binding_receipt_payload_size_bytes",
    "receipt_identity_binding_sha256",
    "retained_identity_payload_sha256",
    "retained_identity_payload_size_bytes",
    "replay_stored_identity_binding_sha256",
    "p83_evidence_state",
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
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class RecoveryStartupReplayStoredIdentityBindingReceiptReplayEvidence:
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
    expected_payload_identity_verified: bool
    canonical_receipt_verified: bool
    dependency_state_verified: bool
    replay_stored_identity_binding_recomputed_verified: bool
    p83_evidence_state: str
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def replay_recovery_startup_replay_stored_identity_binding_receipt(
    payload_utf8: bytes,
    *,
    expected_payload_sha256: str,
    expected_payload_size_bytes: int,
) -> RecoveryStartupReplayStoredIdentityBindingReceiptReplayEvidence:
    """Verify exact P84 receipt bytes and independently recompute the P83 binding."""
    if not isinstance(payload_utf8, bytes):
        raise ValueError("P84 replay-composition receipt payload must be bytes")

    expected_sha = _sha256(expected_payload_sha256, field="expected P84 receipt payload SHA-256")
    expected_size = _positive_int(expected_payload_size_bytes, field="expected P84 receipt payload size")
    if len(payload_utf8) != expected_size:
        raise ValueError("P84 receipt payload byte length mismatch")
    observed_sha = hashlib.sha256(payload_utf8).hexdigest()
    if observed_sha != expected_sha:
        raise ValueError("P84 receipt payload SHA-256 mismatch")

    try:
        text = payload_utf8.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("P84 receipt payload is not valid UTF-8") from exc
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("P84 receipt payload is not valid JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError("P84 receipt payload must decode to a JSON object")
    if set(decoded) != _EXPECTED_KEYS:
        raise ValueError("P84 receipt payload schema is incompatible")
    if decoded["schema"] != P84_SCHEMA:
        raise ValueError("P84 receipt schema identifier is incompatible")

    canonical = json.dumps(decoded, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if canonical != payload_utf8:
        raise ValueError("P84 receipt payload is not strict canonical JSON")
    if decoded["p83_evidence_state"] != P83_EVIDENCE_STATE:
        raise ValueError("P84 receipt P83 evidence state is incompatible")

    sequence = _positive_int(decoded["sequence"], field="P84 sequence")
    lineage = _sha256(decoded["lineage_sha256"], field="P84 lineage SHA-256")
    receipt_sha = _sha256(decoded["binding_receipt_payload_sha256"], field="P84 binding receipt payload SHA-256")
    receipt_size = _positive_int(decoded["binding_receipt_payload_size_bytes"], field="P84 binding receipt payload size")
    receipt_binding = _sha256(decoded["receipt_identity_binding_sha256"], field="P84 receipt identity binding SHA-256")
    retained_sha = _sha256(decoded["retained_identity_payload_sha256"], field="P84 retained identity payload SHA-256")
    retained_size = _positive_int(decoded["retained_identity_payload_size_bytes"], field="P84 retained identity payload size")
    serialized_binding = _sha256(decoded["replay_stored_identity_binding_sha256"], field="P84 replay/stored-identity binding SHA-256")

    recomputed_binding = _canonical_sha({
        "sequence": sequence,
        "lineage_sha256": lineage,
        "binding_receipt_payload_sha256": receipt_sha,
        "binding_receipt_payload_size_bytes": receipt_size,
        "receipt_identity_binding_sha256": receipt_binding,
        "retained_identity_payload_sha256": retained_sha,
        "retained_identity_payload_size_bytes": retained_size,
        "p80_evidence_state": P80_EVIDENCE_STATE,
        "p82_evidence_state": P82_EVIDENCE_STATE,
    })
    if recomputed_binding != serialized_binding:
        raise ValueError("P84 replay/stored-identity binding recomputation mismatch")

    return RecoveryStartupReplayStoredIdentityBindingReceiptReplayEvidence(
        sequence=sequence,
        lineage_sha256=lineage,
        binding_receipt_payload_sha256=receipt_sha,
        binding_receipt_payload_size_bytes=receipt_size,
        receipt_identity_binding_sha256=receipt_binding,
        retained_identity_payload_sha256=retained_sha,
        retained_identity_payload_size_bytes=retained_size,
        replay_stored_identity_binding_sha256=serialized_binding,
        replay_binding_receipt_payload_sha256=observed_sha,
        replay_binding_receipt_payload_size_bytes=len(payload_utf8),
        expected_payload_identity_verified=True,
        canonical_receipt_verified=True,
        dependency_state_verified=True,
        replay_stored_identity_binding_recomputed_verified=True,
        p83_evidence_state=P83_EVIDENCE_STATE,
    )
