"""Replay-verify the locally retained P101 P100-replay identity record.

P102 independently reopens one selected P101 record and verifies exact byte
identity, strict canonical JSON, exact schema, the embedded P100 evidence-state
identity, and semantic agreement with caller-supplied P101 evidence.

This is historical read-only evidence. It does not authenticate the filesystem,
prove freshness or monotonicity, prevent coordinated rollback/replay, or
authorize startup or mutation.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from .recovery_p100 import EVIDENCE_STATE as P100_EVIDENCE_STATE
from .recovery_p101 import (
    EVIDENCE_STATE as P101_EVIDENCE_STATE,
    RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingReceiptReplayIdentityStoreEvidence,
)

EVIDENCE_STATE = (
    "LOCAL_DATA_PLANE_RECOVERY_STARTUP_ADMISSION_STORED_RECEIPT_BINDING_RECEIPT_REPLAY_STORED_IDENTITY_BINDING_"
    "RECEIPT_REPLAY_IDENTITY_STORED_REPLAY_BINDING_RECEIPT_REPLAY_VERIFIED_IDENTITY_STORED_REPLAY_BINDING_RECEIPT_REPLAY_"
    "VERIFIED_IDENTITY_STORED_REPLAY_BINDING_VERIFIED_RECEIPT_REPLAY_VERIFIED_IDENTITY_STORED_VERIFIED"
)
TRUTH_BOUNDARY = (
    "This historical read-only gate proves only that one selected local P101 record matched the caller-supplied P101 evidence during "
    "this call: exact stored byte length and SHA-256, strict canonical JSON, exact schema, embedded P100 evidence-state identity, and "
    "semantic fields were verified. It does not authenticate P101 evidence or the filesystem, prove freshness/latest/global/monotonic "
    "head truth, prevent replay/rollback or coordinated replacement, provide an atomic snapshot after return, rerun P100/P101 or their "
    "dependencies, authorize startup or mutation, provide CAS, leases, fencing, TPM/HSM protection, remote witnessing, distributed "
    "consensus, HA, native-object recovery, cross-process hot swap, production readiness, benchmark evidence, novelty evidence, or "
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
    ("replayed_receipt_retained_identity_binding_receipt_payload_sha256", "sha"),
    ("replayed_receipt_retained_identity_binding_receipt_payload_size_bytes", "int"),
)
_REQUIRED_P101_FLAGS = (
    "p100_evidence_state_verified",
    "p100_verification_flags_verified",
    "exact_readback_verified",
)
_SCHEMA_KEYS = frozenset({field for field, _ in _FIELDS} | {"p100_evidence_state"})


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


def _canonical(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


@dataclass(frozen=True)
class RecoveryP101ReplayEvidence:
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
    stored_payload_sha256: str
    stored_payload_size_bytes: int
    source_path: str
    p101_evidence_state_verified: bool
    p101_verification_flags_verified: bool
    exact_payload_identity_verified: bool
    canonical_record_verified: bool
    semantic_agreement_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def verify_p101_retained_identity(
    evidence: RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingReceiptReplayIdentityStoreEvidence,
    *,
    source_path: str | os.PathLike[str] | None = None,
) -> RecoveryP101ReplayEvidence:
    """Replay-verify one retained P101 identity record against compatible P101 evidence."""
    if not isinstance(
        evidence,
        RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingReceiptReplayIdentityStoreEvidence,
    ):
        raise ValueError("P101 stored replay identity evidence has an incompatible type")
    if evidence.evidence_state != P101_EVIDENCE_STATE:
        raise ValueError("P101 stored replay identity evidence state is incompatible")
    if evidence.automatic_control_allowed is not False:
        raise ValueError("P101 stored replay identity evidence must not grant automatic-control authority")
    if any(getattr(evidence, flag, None) is not True for flag in _REQUIRED_P101_FLAGS):
        raise ValueError("P101 stored replay identity verification flags are incomplete")

    values: dict[str, object] = {}
    for field, kind in _FIELDS:
        raw_value = getattr(evidence, field, None)
        values[field] = (
            _positive_int(raw_value, field=f"P101 {field}")
            if kind == "int"
            else _sha256(raw_value, field=f"P101 {field}")
        )

    stored_sha = _sha256(evidence.stored_payload_sha256, field="P101 stored payload SHA-256")
    stored_size = _positive_int(evidence.stored_payload_size_bytes, field="P101 stored payload size")
    selected = Path(evidence.destination_path if source_path is None else source_path)
    if not selected.name:
        raise ValueError("source path must identify a file")

    raw = selected.read_bytes()
    if len(raw) != stored_size:
        raise ValueError("retained P101 replay identity byte length mismatch")
    if hashlib.sha256(raw).hexdigest() != stored_sha:
        raise ValueError("retained P101 replay identity SHA-256 mismatch")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("retained P101 replay identity is not valid UTF-8") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("retained P101 replay identity is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("retained P101 replay identity must be a JSON object")
    if frozenset(payload) != _SCHEMA_KEYS:
        raise ValueError("retained P101 replay identity schema is incompatible")
    if _canonical(payload) != raw:
        raise ValueError("retained P101 replay identity is not strict canonical JSON")
    if payload.get("p100_evidence_state") != P100_EVIDENCE_STATE:
        raise ValueError("retained P101 replay identity embeds an incompatible P100 evidence state")

    for field, kind in _FIELDS:
        raw_value = payload.get(field)
        parsed = (
            _positive_int(raw_value, field=f"retained P101 {field}")
            if kind == "int"
            else _sha256(raw_value, field=f"retained P101 {field}")
        )
        if parsed != values[field]:
            raise ValueError(f"retained P101 replay identity disagrees on {field}")

    return RecoveryP101ReplayEvidence(
        **values,
        stored_payload_sha256=stored_sha,
        stored_payload_size_bytes=stored_size,
        source_path=str(selected),
        p101_evidence_state_verified=True,
        p101_verification_flags_verified=True,
        exact_payload_identity_verified=True,
        canonical_record_verified=True,
        semantic_agreement_verified=True,
    )
