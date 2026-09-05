"""Replay and independently verify canonical P104 P103-composition receipt bytes.

P105 is read-only replay-consistency evidence. It verifies exact outer byte
identity, strict canonical JSON/schema/state, and independently recomputes P103's
P100/P102 composition binding from the serialized semantic identities. It grants
no startup or mutation authority.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .recovery_p100 import EVIDENCE_STATE as P100_EVIDENCE_STATE
from .recovery_p102 import EVIDENCE_STATE as P102_EVIDENCE_STATE
from .recovery_p103 import EVIDENCE_STATE as P103_EVIDENCE_STATE
from .recovery_p104 import SCHEMA as P104_SCHEMA

EVIDENCE_STATE = (
    "LOCAL_DATA_PLANE_RECOVERY_STARTUP_ADMISSION_STORED_RECEIPT_BINDING_RECEIPT_REPLAY_STORED_IDENTITY_BINDING_"
    "RECEIPT_REPLAY_IDENTITY_STORED_REPLAY_BINDING_RECEIPT_REPLAY_VERIFIED_IDENTITY_STORED_REPLAY_BINDING_RECEIPT_REPLAY_"
    "VERIFIED_IDENTITY_STORED_REPLAY_BINDING_VERIFIED_RECEIPT_REPLAY_VERIFIED_IDENTITY_STORED_VERIFIED_BINDING_VERIFIED_"
    "RECEIPT_CANONICAL_REPLAY_VERIFIED"
)
TRUTH_BOUNDARY = (
    "This read-only gate proves only that supplied P104 receipt bytes matched a caller-supplied expected SHA-256 and byte length, were exact "
    "canonical JSON with the supported schema and P103 evidence-state identity, and contained a P103 P100/P102 replay-composition binding "
    "that recomputed from serialized semantic identities during this call. It does not authenticate the expected byte identity or its source, "
    "establish freshness/latest/global/monotonic head truth, prevent replay or coordinated rollback, rerun P104/P103/P100/P102 or dependencies, "
    "persist or independently retain evidence, provide atomicity after return, authorize startup or mutation, provide CAS, leases, fencing, "
    "TPM/HSM protection, remote witnessing, distributed consensus, HA, native-object recovery, cross-process hot swap, production readiness, "
    "benchmark evidence, novelty evidence, or automatic-control authority."
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
    ("replayed_receipt_retained_identity_binding_receipt_payload_sha256", "sha"),
    ("replayed_receipt_retained_identity_binding_receipt_payload_size_bytes", "int"),
    ("retained_p101_record_payload_sha256", "sha"),
    ("retained_p101_record_payload_size_bytes", "int"),
    ("p100_p102_composition_binding_sha256", "sha"),
)
_BINDING_FIELDS = tuple(field for field, _ in _FIELDS[:25])
_EXPECTED_KEYS = {"schema", "p103_evidence_state", *(field for field, _ in _FIELDS)}


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
class RecoveryP104ReplayEvidence:
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
    expected_payload_identity_verified: bool
    canonical_receipt_verified: bool
    dependency_state_verified: bool
    p100_p102_composition_binding_recomputed_verified: bool
    p103_evidence_state: str
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def replay_p104_composition_receipt(
    payload_utf8: bytes, *, expected_payload_sha256: str, expected_payload_size_bytes: int
) -> RecoveryP104ReplayEvidence:
    """Verify a canonical P104 receipt and independently recompute its P103 binding."""
    if not isinstance(payload_utf8, bytes):
        raise ValueError("P104 P100/P102 composition receipt payload must be bytes")
    expected_sha = _sha256(expected_payload_sha256, field="expected P104 receipt payload SHA-256")
    expected_size = _positive_int(expected_payload_size_bytes, field="expected P104 receipt payload size")
    if len(payload_utf8) != expected_size:
        raise ValueError("P104 receipt payload byte length mismatch")
    observed_sha = hashlib.sha256(payload_utf8).hexdigest()
    if observed_sha != expected_sha:
        raise ValueError("P104 receipt payload SHA-256 mismatch")

    try:
        decoded = json.loads(payload_utf8.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError("P104 receipt payload is not valid UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("P104 receipt payload is not valid JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError("P104 receipt payload must decode to a JSON object")
    if set(decoded) != _EXPECTED_KEYS or decoded["schema"] != P104_SCHEMA:
        raise ValueError("P104 receipt payload schema is incompatible")

    canonical = json.dumps(decoded, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if canonical != payload_utf8:
        raise ValueError("P104 receipt payload is not strict canonical JSON")
    if decoded["p103_evidence_state"] != P103_EVIDENCE_STATE:
        raise ValueError("P104 receipt P103 evidence state is incompatible")

    values = {
        field: (
            _positive_int(decoded[field], field=f"P104 {field}")
            if kind == "int"
            else _sha256(decoded[field], field=f"P104 {field}")
        )
        for field, kind in _FIELDS
    }
    serialized_binding = values["p100_p102_composition_binding_sha256"]
    binding_inputs = {field: values[field] for field in _BINDING_FIELDS}
    recomputed_binding = _canonical_sha(
        {
            **binding_inputs,
            "retained_p101_record_payload_sha256": values["retained_p101_record_payload_sha256"],
            "retained_p101_record_payload_size_bytes": values["retained_p101_record_payload_size_bytes"],
            "p100_evidence_state": P100_EVIDENCE_STATE,
            "p102_evidence_state": P102_EVIDENCE_STATE,
        }
    )
    if recomputed_binding != serialized_binding:
        raise ValueError("P104 P100/P102 composition binding recomputation mismatch")

    return RecoveryP104ReplayEvidence(
        **values,
        p104_receipt_payload_sha256=observed_sha,
        p104_receipt_payload_size_bytes=len(payload_utf8),
        expected_payload_identity_verified=True,
        canonical_receipt_verified=True,
        dependency_state_verified=True,
        p100_p102_composition_binding_recomputed_verified=True,
        p103_evidence_state=P103_EVIDENCE_STATE,
    )
