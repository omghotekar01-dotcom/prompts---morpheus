"""Replay and independently verify canonical P109 P108-composition receipt bytes.

P110 is read-only replay-consistency evidence. It verifies exact outer byte
identity, strict canonical JSON/schema/state, and independently recomputes P108's
P105/P107 composition binding from the serialized semantic identities. It grants
no startup or mutation authority.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .recovery_p103 import EVIDENCE_STATE as P103_EVIDENCE_STATE
from .recovery_p105 import EVIDENCE_STATE as P105_EVIDENCE_STATE
from .recovery_p107 import EVIDENCE_STATE as P107_EVIDENCE_STATE
from .recovery_p108 import EVIDENCE_STATE as P108_EVIDENCE_STATE, _FIELDS as P108_SHARED_FIELDS
from .recovery_p109 import SCHEMA as P109_SCHEMA, _FIELDS as P109_FIELDS

EVIDENCE_STATE = P108_EVIDENCE_STATE + "_RECEIPT_CANONICAL_REPLAY_VERIFIED"
TRUTH_BOUNDARY = (
    "This read-only gate proves only that supplied P109 receipt bytes matched a caller-supplied expected SHA-256 and byte length, were exact "
    "canonical JSON with the supported schema and P108 evidence-state identity, and contained a P108 P105/P107 replay-composition binding "
    "that recomputed from serialized semantic identities during this call. It does not authenticate the expected byte identity or its source, "
    "establish freshness/latest/global/monotonic head truth, prevent replay or coordinated rollback, rerun P109/P108/P105/P107 or dependencies, "
    "persist or independently retain evidence, provide atomicity after return, authorize startup or mutation, provide CAS, leases, fencing, "
    "TPM/HSM protection, remote witnessing, distributed consensus, HA, native-object recovery, cross-process hot swap, production readiness, "
    "benchmark evidence, novelty evidence, or automatic-control authority."
)

_FIELDS = P109_FIELDS
_EXPECTED_KEYS = {"schema", "p108_evidence_state", *(field for field, _ in _FIELDS)}


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
class RecoveryP109ReplayEvidence:
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
    p104_receipt_payload_sha256: str
    p104_receipt_payload_size_bytes: int
    retained_p106_record_payload_sha256: str
    retained_p106_record_payload_size_bytes: int
    p105_p107_composition_binding_sha256: str
    p109_receipt_payload_sha256: str
    p109_receipt_payload_size_bytes: int
    expected_payload_identity_verified: bool
    canonical_receipt_verified: bool
    dependency_state_verified: bool
    p105_p107_composition_binding_recomputed_verified: bool
    p108_evidence_state: str
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def replay_p109_composition_receipt(
    payload_utf8: bytes, *, expected_payload_sha256: str, expected_payload_size_bytes: int
) -> RecoveryP109ReplayEvidence:
    """Verify a canonical P109 receipt and independently recompute its P108 binding."""
    if not isinstance(payload_utf8, bytes):
        raise ValueError("P109 P105/P107 composition receipt payload must be bytes")
    expected_sha = _sha256(expected_payload_sha256, field="expected P109 receipt payload SHA-256")
    expected_size = _positive_int(expected_payload_size_bytes, field="expected P109 receipt payload size")
    if len(payload_utf8) != expected_size:
        raise ValueError("P109 receipt payload byte length mismatch")
    observed_sha = hashlib.sha256(payload_utf8).hexdigest()
    if observed_sha != expected_sha:
        raise ValueError("P109 receipt payload SHA-256 mismatch")

    try:
        decoded = json.loads(payload_utf8.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError("P109 receipt payload is not valid UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("P109 receipt payload is not valid JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError("P109 receipt payload must decode to a JSON object")
    if set(decoded) != _EXPECTED_KEYS or decoded["schema"] != P109_SCHEMA:
        raise ValueError("P109 receipt payload schema is incompatible")

    canonical = json.dumps(decoded, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if canonical != payload_utf8:
        raise ValueError("P109 receipt payload is not strict canonical JSON")
    if decoded["p108_evidence_state"] != P108_EVIDENCE_STATE:
        raise ValueError("P109 receipt P108 evidence state is incompatible")

    values = {
        field: (
            _positive_int(decoded[field], field=f"P109 {field}")
            if kind == "int"
            else _sha256(decoded[field], field=f"P109 {field}")
        )
        for field, kind in _FIELDS
    }
    serialized_binding = values["p105_p107_composition_binding_sha256"]
    shared_values = {field: values[field] for field, _ in P108_SHARED_FIELDS}
    recomputed_binding = _canonical_sha(
        {
            **shared_values,
            "retained_p106_record_payload_sha256": values["retained_p106_record_payload_sha256"],
            "retained_p106_record_payload_size_bytes": values["retained_p106_record_payload_size_bytes"],
            "p103_evidence_state": P103_EVIDENCE_STATE,
            "p105_evidence_state": P105_EVIDENCE_STATE,
            "p107_evidence_state": P107_EVIDENCE_STATE,
        }
    )
    if recomputed_binding != serialized_binding:
        raise ValueError("P109 P105/P107 composition binding recomputation mismatch")

    return RecoveryP109ReplayEvidence(
        **values,
        p109_receipt_payload_sha256=observed_sha,
        p109_receipt_payload_size_bytes=len(payload_utf8),
        expected_payload_identity_verified=True,
        canonical_receipt_verified=True,
        dependency_state_verified=True,
        p105_p107_composition_binding_recomputed_verified=True,
        p108_evidence_state=P108_EVIDENCE_STATE,
    )
