"""Replay and independently verify canonical P124 P123-composition receipt bytes.

P125 is read-only replay-consistency evidence. It verifies exact outer byte
identity, strict canonical JSON/schema/state, and independently recomputes P123's
P120/P122 composition binding from serialized semantic identities. It grants
no startup or mutation authority.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import make_dataclass

from .recovery_p118 import EVIDENCE_STATE as P118_EVIDENCE_STATE
from .recovery_p120 import EVIDENCE_STATE as P120_EVIDENCE_STATE
from .recovery_p122 import EVIDENCE_STATE as P122_EVIDENCE_STATE
from .recovery_p123 import EVIDENCE_STATE as P123_EVIDENCE_STATE, _FIELDS as P123_SHARED_FIELDS
from .recovery_p124 import SCHEMA as P124_SCHEMA, _FIELDS as P124_FIELDS

EVIDENCE_STATE = P123_EVIDENCE_STATE + "_RECEIPT_CANONICAL_REPLAY_VERIFIED"
TRUTH_BOUNDARY = (
    "This read-only gate proves only that supplied P124 receipt bytes matched a caller-supplied expected SHA-256 and byte length, were exact "
    "canonical JSON with the supported schema and P123 evidence-state identity, and contained a P123 P120/P122 replay-composition binding "
    "that recomputed from serialized semantic identities during this call. It does not authenticate the expected byte identity or its source, "
    "establish freshness/latest/global/monotonic head truth, prevent replay or coordinated rollback, rerun P124/P123/P120/P122 or dependencies, "
    "persist or independently retain evidence, provide atomicity after return, authorize startup or mutation, provide CAS, leases, fencing, "
    "TPM/HSM protection, remote witnessing, distributed consensus, HA, native-object recovery, cross-process hot swap, production readiness, "
    "benchmark evidence, novelty evidence, or automatic-control authority."
)

_FIELDS = P124_FIELDS
_EXPECTED_KEYS = {"schema", "p123_evidence_state", *(field for field, _ in _FIELDS)}


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


RecoveryP124ReplayEvidence = make_dataclass(
    "RecoveryP124ReplayEvidence",
    [
        *((field, int if kind == "int" else str) for field, kind in _FIELDS),
        ("p124_receipt_payload_sha256", str),
        ("p124_receipt_payload_size_bytes", int),
        ("expected_payload_identity_verified", bool),
        ("canonical_receipt_verified", bool),
        ("dependency_state_verified", bool),
        ("p120_p122_composition_binding_recomputed_verified", bool),
        ("p123_evidence_state", str),
        ("evidence_state", str, EVIDENCE_STATE),
        ("automatic_control_allowed", bool, False),
    ],
    frozen=True,
    namespace={"as_dict": lambda self: {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}},
)


def replay_p124_composition_receipt(
    payload_utf8: bytes, *, expected_payload_sha256: str, expected_payload_size_bytes: int
) -> RecoveryP124ReplayEvidence:
    """Verify a canonical P124 receipt and independently recompute its P123 binding."""
    if not isinstance(payload_utf8, bytes):
        raise ValueError("P124 P120/P122 composition receipt payload must be bytes")
    expected_sha = _sha256(expected_payload_sha256, field="expected P124 receipt payload SHA-256")
    expected_size = _positive_int(expected_payload_size_bytes, field="expected P124 receipt payload size")
    if len(payload_utf8) != expected_size:
        raise ValueError("P124 receipt payload byte length mismatch")
    observed_sha = hashlib.sha256(payload_utf8).hexdigest()
    if observed_sha != expected_sha:
        raise ValueError("P124 receipt payload SHA-256 mismatch")

    try:
        decoded = json.loads(payload_utf8.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError("P124 receipt payload is not valid UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("P124 receipt payload is not valid JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError("P124 receipt payload must decode to a JSON object")
    if set(decoded) != _EXPECTED_KEYS or decoded["schema"] != P124_SCHEMA:
        raise ValueError("P124 receipt payload schema is incompatible")

    canonical = json.dumps(decoded, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if canonical != payload_utf8:
        raise ValueError("P124 receipt payload is not strict canonical JSON")
    if decoded["p123_evidence_state"] != P123_EVIDENCE_STATE:
        raise ValueError("P124 receipt P123 evidence state is incompatible")

    values = {
        field: (
            _positive_int(decoded[field], field=f"P124 {field}")
            if kind == "int"
            else _sha256(decoded[field], field=f"P124 {field}")
        )
        for field, kind in _FIELDS
    }
    serialized_binding = values["p120_p122_composition_binding_sha256"]
    shared_values = {field: values[field] for field, _ in P123_SHARED_FIELDS}
    recomputed_binding = _canonical_sha(
        {
            **shared_values,
            "retained_p121_record_payload_sha256": values["retained_p121_record_payload_sha256"],
            "retained_p121_record_payload_size_bytes": values["retained_p121_record_payload_size_bytes"],
            "p118_evidence_state": P118_EVIDENCE_STATE,
            "p120_evidence_state": P120_EVIDENCE_STATE,
            "p122_evidence_state": P122_EVIDENCE_STATE,
        }
    )
    if recomputed_binding != serialized_binding:
        raise ValueError("P124 P120/P122 composition binding recomputation mismatch")

    return RecoveryP124ReplayEvidence(
        **values,
        p124_receipt_payload_sha256=observed_sha,
        p124_receipt_payload_size_bytes=len(payload_utf8),
        expected_payload_identity_verified=True,
        canonical_receipt_verified=True,
        dependency_state_verified=True,
        p120_p122_composition_binding_recomputed_verified=True,
        p123_evidence_state=P123_EVIDENCE_STATE,
    )
