from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from .process_transfer_fencing_receipt_restart import BracketedFencedRestartCurrentnessVerification


RECEIPT_SCHEMA = "morpheus.fenced-restart-bracketed-currentness-receipt.v1"
EVIDENCE_STATE = "VERIFIED_CANONICAL_BRACKETED_RESTART_OBSERVATION_RECEIPT_NO_CUTOVER_AUTHORITY"
TRUTH_BOUNDARY = (
    "This receipt canonically records and replays the exact identities and two equal external fencing-counter observations "
    "already returned by a successful BracketedFencedRestartCurrentnessVerification. It is historical evidence binding only. "
    "Receipt replay does not call the external fencing authority, re-run local head/bundle verification, prove that the fencing "
    "counter is current at replay time, prove that it remained unchanged between the two recorded reads, establish an atomic "
    "snapshot, lease, lock, consensus or safe cutover, or authorize activation, automatic control or traffic switching. "
    "MORPHEUS does not attest correctness, linearizability, durability, availability or compromise resistance of the external "
    "authority. No benchmark, performance, novelty, scientific-effect, HA/SLA or production-readiness claim is made."
)

_FIELDS = (
    "schema",
    "source_receipt_sha256",
    "key_id",
    "authority_id",
    "sequence",
    "head_sha256",
    "bundle_sha256",
    "migration_id",
    "session_id",
    "target_candidate_id",
    "fencing_authority_id",
    "previous_fencing_counter",
    "fencing_counter",
    "observed_fencing_counter_before",
    "observed_fencing_counter_after",
    "receipt_replay_verified",
    "pre_replay_counter_observation_verified",
    "local_restart_evidence_reverified",
    "exact_receipt_local_binding_verified",
    "post_replay_counter_observation_verified",
    "bracketed_counter_equality_verified",
    "automatic_control_allowed",
    "activation_allowed",
    "traffic_switching_allowed",
    "source_evidence_state",
)


@dataclass(frozen=True)
class BracketedRestartObservationReceiptVerification:
    evidence_receipt_sha256: str
    evidence_receipt_size_bytes: int
    source_receipt_sha256: str
    key_id: str
    authority_id: str
    sequence: int
    head_sha256: str
    bundle_sha256: str
    migration_id: str
    session_id: str
    target_candidate_id: str
    fencing_authority_id: str
    previous_fencing_counter: int
    fencing_counter: int
    observed_fencing_counter_before: int
    observed_fencing_counter_after: int
    canonical_encoding_verified: bool = True
    exact_identity_binding_verified: bool = True
    historical_observation_binding_only: bool = True
    automatic_control_allowed: bool = False
    activation_allowed: bool = False
    traffic_switching_allowed: bool = False
    evidence_state: str = EVIDENCE_STATE
    truth_boundary: str = TRUTH_BOUNDARY


def _canonical(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"bracketed receipt contains duplicate JSON key: {key}")
        out[key] = value
    return out


def _identity(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or "\n" in value or "\r" in value:
        raise ValueError(f"bracketed receipt {field} must be a non-empty single-line string")
    return value


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"bracketed receipt {field} must be a lowercase SHA-256 hex digest")
    return value


def _positive_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"bracketed receipt {field} must be a positive integer")
    return value


def _counter(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"bracketed receipt {field} must be a non-negative integer")
    return value


def _validate(payload: Mapping[str, Any]) -> None:
    if set(payload) != set(_FIELDS):
        raise ValueError("bracketed receipt schema fields mismatch")
    if payload["schema"] != RECEIPT_SCHEMA:
        raise ValueError("bracketed receipt schema identity mismatch")

    for field in (
        "key_id",
        "authority_id",
        "migration_id",
        "session_id",
        "target_candidate_id",
        "fencing_authority_id",
        "source_evidence_state",
    ):
        _identity(payload[field], field)
    _sha(payload["source_receipt_sha256"], "source_receipt_sha256")
    _sha(payload["head_sha256"], "head_sha256")
    _sha(payload["bundle_sha256"], "bundle_sha256")
    _positive_int(payload["sequence"], "sequence")

    previous = _counter(payload["previous_fencing_counter"], "previous_fencing_counter")
    current = _counter(payload["fencing_counter"], "fencing_counter")
    before = _counter(payload["observed_fencing_counter_before"], "observed_fencing_counter_before")
    after = _counter(payload["observed_fencing_counter_after"], "observed_fencing_counter_after")
    if current != previous + 1:
        raise ValueError("bracketed receipt fencing_counter must be exactly previous_fencing_counter + 1")
    if before != current or after != current:
        raise ValueError("bracketed receipt observations must both equal fencing_counter")

    for field in (
        "receipt_replay_verified",
        "pre_replay_counter_observation_verified",
        "local_restart_evidence_reverified",
        "exact_receipt_local_binding_verified",
        "post_replay_counter_observation_verified",
        "bracketed_counter_equality_verified",
    ):
        if payload[field] is not True:
            raise ValueError(f"bracketed receipt {field} must be true")
    for field in ("automatic_control_allowed", "activation_allowed", "traffic_switching_allowed"):
        if payload[field] is not False:
            raise ValueError(f"bracketed receipt {field} must be false")


def encode_bracketed_restart_observation_receipt(
    verification: BracketedFencedRestartCurrentnessVerification,
) -> bytes:
    if not isinstance(verification, BracketedFencedRestartCurrentnessVerification):
        raise TypeError("verification must be BracketedFencedRestartCurrentnessVerification")
    payload = {
        "schema": RECEIPT_SCHEMA,
        "source_receipt_sha256": verification.receipt_sha256,
        "key_id": verification.key_id,
        "authority_id": verification.authority_id,
        "sequence": verification.sequence,
        "head_sha256": verification.head_sha256,
        "bundle_sha256": verification.bundle_sha256,
        "migration_id": verification.migration_id,
        "session_id": verification.session_id,
        "target_candidate_id": verification.target_candidate_id,
        "fencing_authority_id": verification.fencing_authority_id,
        "previous_fencing_counter": verification.previous_fencing_counter,
        "fencing_counter": verification.fencing_counter,
        "observed_fencing_counter_before": verification.observed_fencing_counter_before,
        "observed_fencing_counter_after": verification.observed_fencing_counter_after,
        "receipt_replay_verified": verification.receipt_replay_verified,
        "pre_replay_counter_observation_verified": verification.pre_replay_counter_observation_verified,
        "local_restart_evidence_reverified": verification.local_restart_evidence_reverified,
        "exact_receipt_local_binding_verified": verification.exact_receipt_local_binding_verified,
        "post_replay_counter_observation_verified": verification.post_replay_counter_observation_verified,
        "bracketed_counter_equality_verified": verification.bracketed_counter_equality_verified,
        "automatic_control_allowed": verification.automatic_control_allowed,
        "activation_allowed": verification.activation_allowed,
        "traffic_switching_allowed": verification.traffic_switching_allowed,
        "source_evidence_state": verification.evidence_state,
    }
    _validate(payload)
    return _canonical(payload)


def verify_bracketed_restart_observation_receipt(
    receipt_bytes: bytes,
    *,
    expected_source_receipt_sha256: str,
    expected_key_id: str,
    expected_authority_id: str,
    expected_sequence: int,
    expected_head_sha256: str,
    expected_bundle_sha256: str,
    expected_migration_id: str,
    expected_session_id: str,
    expected_target_candidate_id: str,
    expected_fencing_authority_id: str,
    expected_previous_fencing_counter: int,
    expected_fencing_counter: int,
) -> BracketedRestartObservationReceiptVerification:
    if not isinstance(receipt_bytes, bytes):
        raise TypeError("receipt_bytes must be bytes")
    try:
        payload = json.loads(receipt_bytes.decode("utf-8"), object_pairs_hook=_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("bracketed receipt is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("bracketed receipt root must be an object")
    _validate(payload)
    if _canonical(payload) != receipt_bytes:
        raise ValueError("bracketed receipt bytes are not canonical")

    expected = {
        "source_receipt_sha256": _sha(expected_source_receipt_sha256, "expected_source_receipt_sha256"),
        "key_id": _identity(expected_key_id, "expected_key_id"),
        "authority_id": _identity(expected_authority_id, "expected_authority_id"),
        "sequence": _positive_int(expected_sequence, "expected_sequence"),
        "head_sha256": _sha(expected_head_sha256, "expected_head_sha256"),
        "bundle_sha256": _sha(expected_bundle_sha256, "expected_bundle_sha256"),
        "migration_id": _identity(expected_migration_id, "expected_migration_id"),
        "session_id": _identity(expected_session_id, "expected_session_id"),
        "target_candidate_id": _identity(expected_target_candidate_id, "expected_target_candidate_id"),
        "fencing_authority_id": _identity(expected_fencing_authority_id, "expected_fencing_authority_id"),
        "previous_fencing_counter": _counter(expected_previous_fencing_counter, "expected_previous_fencing_counter"),
        "fencing_counter": _counter(expected_fencing_counter, "expected_fencing_counter"),
    }
    if expected["fencing_counter"] != expected["previous_fencing_counter"] + 1:
        raise ValueError("expected_fencing_counter must be exactly expected_previous_fencing_counter + 1")
    for field, value in expected.items():
        if payload[field] != value:
            raise ValueError(f"bracketed receipt {field} does not match expected identity")

    return BracketedRestartObservationReceiptVerification(
        evidence_receipt_sha256=hashlib.sha256(receipt_bytes).hexdigest(),
        evidence_receipt_size_bytes=len(receipt_bytes),
        source_receipt_sha256=payload["source_receipt_sha256"],
        key_id=payload["key_id"],
        authority_id=payload["authority_id"],
        sequence=payload["sequence"],
        head_sha256=payload["head_sha256"],
        bundle_sha256=payload["bundle_sha256"],
        migration_id=payload["migration_id"],
        session_id=payload["session_id"],
        target_candidate_id=payload["target_candidate_id"],
        fencing_authority_id=payload["fencing_authority_id"],
        previous_fencing_counter=payload["previous_fencing_counter"],
        fencing_counter=payload["fencing_counter"],
        observed_fencing_counter_before=payload["observed_fencing_counter_before"],
        observed_fencing_counter_after=payload["observed_fencing_counter_after"],
    )
