"""Replay and independently verify canonical P99 P98-composition receipt bytes.

P100 is the consumer-side counterpart to P99. A caller supplies exact P99 receipt
bytes with an expected byte length and SHA-256. This gate verifies the outer byte
identity, strict canonical JSON and exact schema, validates the embedded P98
state contract, and independently recomputes P98's P95/P97 composition binding
from serialized semantic identities rather than trusting the serialized value.

This is read-only replay-consistency evidence. It does not authenticate the
expected identity, establish freshness or rollback resistance, or authorize
startup or mutation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay import (
    EVIDENCE_STATE as P95_EVIDENCE_STATE,
)
from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay import (
    EVIDENCE_STATE as P97_EVIDENCE_STATE,
)
from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding import (
    EVIDENCE_STATE as P98_EVIDENCE_STATE,
)
from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt import (
    SCHEMA as P99_SCHEMA,
)

EVIDENCE_STATE = (
    "LOCAL_DATA_PLANE_RECOVERY_STARTUP_ADMISSION_STORED_RECEIPT_BINDING_RECEIPT_REPLAY_STORED_IDENTITY_BINDING_"
    "RECEIPT_REPLAY_IDENTITY_STORED_REPLAY_BINDING_RECEIPT_REPLAY_VERIFIED_IDENTITY_STORED_REPLAY_BINDING_RECEIPT_REPLAY_"
    "VERIFIED_IDENTITY_STORED_REPLAY_BINDING_VERIFIED_RECEIPT_REPLAY_VERIFIED"
)
TRUTH_BOUNDARY = (
    "This read-only gate proves only that supplied P99 receipt bytes matched a caller-supplied expected SHA-256 and byte length, were exact canonical "
    "JSON with the supported schema and P98 evidence-state identity, and contained a P98 P95/P97 replay-composition binding that recomputed from "
    "serialized semantic identities during this call. It does not authenticate the expected byte identity or its source, establish freshness/latest/"
    "global/monotonic head truth, prevent replay or coordinated rollback, rerun P99/P98/P95/P97 or dependencies, persist or independently retain "
    "evidence, provide atomicity after return, authorize startup or mutation, provide CAS, leases, fencing, TPM/HSM protection, remote witnessing, "
    "distributed consensus, HA, native-object recovery, cross-process hot swap, production readiness, benchmark evidence, novelty evidence, or "
    "automatic-control authority."
)

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
_EXPECTED_KEYS = {"schema", "p98_evidence_state", *(field for field, _ in _FIELDS)}


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


def _canonical_sha(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingReceiptReplayEvidence:
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
    expected_payload_identity_verified: bool
    canonical_receipt_verified: bool
    dependency_state_verified: bool
    replayed_receipt_retained_identity_binding_recomputed_verified: bool
    p98_evidence_state: str
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def replay_recovery_startup_replayed_receipt_retained_identity_binding_receipt(
    payload_utf8: bytes,
    *,
    expected_payload_sha256: str,
    expected_payload_size_bytes: int,
) -> RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingReceiptReplayEvidence:
    """Verify exact P99 bytes and independently recompute the P98 binding."""
    if not isinstance(payload_utf8, bytes):
        raise ValueError("P99 P95/P97 replay-composition binding receipt payload must be bytes")

    expected_sha = _sha256(expected_payload_sha256, field="expected P99 receipt payload SHA-256")
    expected_size = _positive_int(expected_payload_size_bytes, field="expected P99 receipt payload size")
    if len(payload_utf8) != expected_size:
        raise ValueError("P99 receipt payload byte length mismatch")
    observed_sha = hashlib.sha256(payload_utf8).hexdigest()
    if observed_sha != expected_sha:
        raise ValueError("P99 receipt payload SHA-256 mismatch")

    try:
        decoded = json.loads(payload_utf8.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError("P99 receipt payload is not valid UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("P99 receipt payload is not valid JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError("P99 receipt payload must decode to a JSON object")
    if set(decoded) != _EXPECTED_KEYS:
        raise ValueError("P99 receipt payload schema is incompatible")
    if decoded["schema"] != P99_SCHEMA:
        raise ValueError("P99 receipt schema identifier is incompatible")

    canonical = json.dumps(decoded, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if canonical != payload_utf8:
        raise ValueError("P99 receipt payload is not strict canonical JSON")
    if decoded["p98_evidence_state"] != P98_EVIDENCE_STATE:
        raise ValueError("P99 receipt P98 evidence state is incompatible")

    values: dict[str, object] = {}
    for field, kind in _FIELDS:
        raw = decoded[field]
        values[field] = _positive_int(raw, field=f"P99 {field}") if kind == "int" else _sha256(raw, field=f"P99 {field}")

    serialized_binding = values["replayed_receipt_retained_identity_binding_sha256"]
    binding_inputs = {
        field: values[field]
        for field, _ in _FIELDS
        if field != "replayed_receipt_retained_identity_binding_sha256"
    }
    recomputed_binding = _canonical_sha(
        {
            **binding_inputs,
            "p95_evidence_state": P95_EVIDENCE_STATE,
            "p97_evidence_state": P97_EVIDENCE_STATE,
        }
    )
    if recomputed_binding != serialized_binding:
        raise ValueError("P99 replayed-receipt/retained-identity binding recomputation mismatch")

    return RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingReceiptReplayEvidence(
        **values,
        replayed_receipt_retained_identity_binding_receipt_payload_sha256=observed_sha,
        replayed_receipt_retained_identity_binding_receipt_payload_size_bytes=len(payload_utf8),
        expected_payload_identity_verified=True,
        canonical_receipt_verified=True,
        dependency_state_verified=True,
        replayed_receipt_retained_identity_binding_recomputed_verified=True,
        p98_evidence_state=P98_EVIDENCE_STATE,
    )
