"""Replay and independently verify canonical P89 replay/retained-identity binding receipt bytes.

P90 is the consumer-side counterpart to P89. A caller supplies exact P89 receipt
bytes with an expected byte length and SHA-256. This gate verifies the outer byte
identity, strict canonical JSON and exact schema, validates the embedded P88
state contract, and independently recomputes the P88 P85/P87 composition binding
from serialized semantic identities rather than trusting the serialized value.

This is read-only replay-consistency evidence. It does not authenticate the
expected identity, establish freshness or rollback resistance, or authorize
startup or mutation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay import (
    EVIDENCE_STATE as P85_EVIDENCE_STATE,
)
from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay import (
    EVIDENCE_STATE as P87_EVIDENCE_STATE,
)
from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding import (
    EVIDENCE_STATE as P88_EVIDENCE_STATE,
)
from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt import (
    SCHEMA as P89_SCHEMA,
)

EVIDENCE_STATE = (
    "LOCAL_DATA_PLANE_RECOVERY_STARTUP_ADMISSION_STORED_RECEIPT_BINDING_RECEIPT_REPLAY_STORED_IDENTITY_BINDING_"
    "RECEIPT_REPLAY_IDENTITY_STORED_REPLAY_BINDING_RECEIPT_REPLAY_VERIFIED"
)
TRUTH_BOUNDARY = (
    "This read-only gate proves only that supplied P89 receipt bytes matched a caller-supplied expected SHA-256 and byte length, were exact "
    "canonical JSON with the supported schema and P88 evidence-state identity, and contained a P88 P85/P87 replay/retained-identity composition "
    "binding that recomputed from serialized semantic identities during this call. It does not authenticate the expected byte identity or its "
    "source, establish freshness/latest/global/monotonic head truth, prevent replay or coordinated rollback, rerun P89/P88/P85/P87 or dependencies, "
    "persist or independently retain evidence, provide atomicity after return, authorize startup or mutation, provide CAS, leases, fencing, TPM/HSM "
    "protection, remote witnessing, distributed consensus, HA, native-object recovery, cross-process hot swap, production readiness, benchmark evidence, "
    "novelty evidence, or automatic-control authority."
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
    "replay_binding_receipt_payload_sha256",
    "replay_binding_receipt_payload_size_bytes",
    "retained_replay_identity_payload_sha256",
    "retained_replay_identity_payload_size_bytes",
    "replay_retained_identity_binding_sha256",
    "p88_evidence_state",
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
class RecoveryStartupReplayRetainedIdentityBindingReceiptReplayEvidence:
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
    expected_payload_identity_verified: bool
    canonical_receipt_verified: bool
    dependency_state_verified: bool
    replay_retained_identity_binding_recomputed_verified: bool
    p88_evidence_state: str
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def replay_recovery_startup_replay_retained_identity_binding_receipt(
    payload_utf8: bytes,
    *,
    expected_payload_sha256: str,
    expected_payload_size_bytes: int,
) -> RecoveryStartupReplayRetainedIdentityBindingReceiptReplayEvidence:
    """Verify exact P89 receipt bytes and independently recompute the P88 binding."""
    if not isinstance(payload_utf8, bytes):
        raise ValueError("P89 replay/retained-identity binding receipt payload must be bytes")

    expected_sha = _sha256(expected_payload_sha256, field="expected P89 receipt payload SHA-256")
    expected_size = _positive_int(expected_payload_size_bytes, field="expected P89 receipt payload size")
    if len(payload_utf8) != expected_size:
        raise ValueError("P89 receipt payload byte length mismatch")
    observed_sha = hashlib.sha256(payload_utf8).hexdigest()
    if observed_sha != expected_sha:
        raise ValueError("P89 receipt payload SHA-256 mismatch")

    try:
        text = payload_utf8.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("P89 receipt payload is not valid UTF-8") from exc
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("P89 receipt payload is not valid JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError("P89 receipt payload must decode to a JSON object")
    if set(decoded) != _EXPECTED_KEYS:
        raise ValueError("P89 receipt payload schema is incompatible")
    if decoded["schema"] != P89_SCHEMA:
        raise ValueError("P89 receipt schema identifier is incompatible")

    canonical = json.dumps(decoded, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if canonical != payload_utf8:
        raise ValueError("P89 receipt payload is not strict canonical JSON")
    if decoded["p88_evidence_state"] != P88_EVIDENCE_STATE:
        raise ValueError("P89 receipt P88 evidence state is incompatible")

    sequence = _positive_int(decoded["sequence"], field="P89 sequence")
    lineage = _sha256(decoded["lineage_sha256"], field="P89 lineage SHA-256")
    binding_receipt_sha = _sha256(decoded["binding_receipt_payload_sha256"], field="P89 binding receipt payload SHA-256")
    binding_receipt_size = _positive_int(decoded["binding_receipt_payload_size_bytes"], field="P89 binding receipt payload size")
    receipt_identity_binding = _sha256(decoded["receipt_identity_binding_sha256"], field="P89 receipt identity binding SHA-256")
    retained_identity_sha = _sha256(decoded["retained_identity_payload_sha256"], field="P89 retained identity payload SHA-256")
    retained_identity_size = _positive_int(decoded["retained_identity_payload_size_bytes"], field="P89 retained identity payload size")
    replay_stored_binding = _sha256(decoded["replay_stored_identity_binding_sha256"], field="P89 replay/stored-identity binding SHA-256")
    replay_receipt_sha = _sha256(decoded["replay_binding_receipt_payload_sha256"], field="P89 replay binding receipt payload SHA-256")
    replay_receipt_size = _positive_int(decoded["replay_binding_receipt_payload_size_bytes"], field="P89 replay binding receipt payload size")
    retained_replay_sha = _sha256(decoded["retained_replay_identity_payload_sha256"], field="P89 retained replay identity payload SHA-256")
    retained_replay_size = _positive_int(decoded["retained_replay_identity_payload_size_bytes"], field="P89 retained replay identity payload size")
    serialized_binding = _sha256(decoded["replay_retained_identity_binding_sha256"], field="P89 replay/retained-identity binding SHA-256")

    recomputed_binding = _canonical_sha({
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
        "p85_evidence_state": P85_EVIDENCE_STATE,
        "p87_evidence_state": P87_EVIDENCE_STATE,
    })
    if recomputed_binding != serialized_binding:
        raise ValueError("P89 replay/retained-identity binding recomputation mismatch")

    return RecoveryStartupReplayRetainedIdentityBindingReceiptReplayEvidence(
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
        replay_retained_identity_binding_sha256=serialized_binding,
        replay_retained_identity_binding_receipt_payload_sha256=observed_sha,
        replay_retained_identity_binding_receipt_payload_size_bytes=len(payload_utf8),
        expected_payload_identity_verified=True,
        canonical_receipt_verified=True,
        dependency_state_verified=True,
        replay_retained_identity_binding_recomputed_verified=True,
        p88_evidence_state=P88_EVIDENCE_STATE,
    )
