"""Replay-verify one locally retained P106 P105-replay identity record.

P107 independently reopens one selected P106 record and verifies exact byte
identity, strict canonical JSON, exact schema, the embedded P105 evidence-state
identity, and semantic agreement with caller-supplied P106 store evidence.

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

from .recovery_p105 import EVIDENCE_STATE as P105_EVIDENCE_STATE
from .recovery_p106 import EVIDENCE_STATE as P106_EVIDENCE_STATE, RecoveryP105ReplayIdentityStoreEvidence

EVIDENCE_STATE = P106_EVIDENCE_STATE + "_REPLAY_VERIFIED"
TRUTH_BOUNDARY = (
    "This historical read-only gate proves only that one selected local P106 record matched the caller-supplied P106 evidence during "
    "this call: exact stored byte length and SHA-256, strict canonical JSON, exact schema, embedded P105 evidence-state identity, and "
    "semantic fields were verified. It does not authenticate P106 evidence or the filesystem, prove freshness/latest/global/monotonic "
    "head truth, prevent replay/rollback or coordinated replacement, provide an atomic snapshot after return, rerun P105/P106 or their "
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
    ("retained_p101_record_payload_sha256", "sha"),
    ("retained_p101_record_payload_size_bytes", "int"),
    ("p100_p102_composition_binding_sha256", "sha"),
    ("p104_receipt_payload_sha256", "sha"),
    ("p104_receipt_payload_size_bytes", "int"),
)
_REQUIRED_P106_FLAGS = (
    "p105_evidence_state_verified",
    "p105_verification_flags_verified",
    "exact_readback_verified",
)
_SCHEMA_KEYS = frozenset({field for field, _ in _FIELDS} | {"p105_evidence_state"})


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
class RecoveryP106ReplayEvidence:
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
    stored_payload_sha256: str
    stored_payload_size_bytes: int
    source_path: str
    p106_evidence_state_verified: bool
    p106_verification_flags_verified: bool
    exact_payload_identity_verified: bool
    canonical_record_verified: bool
    semantic_agreement_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def verify_p106_retained_identity(
    evidence: RecoveryP105ReplayIdentityStoreEvidence,
    *,
    source_path: str | os.PathLike[str] | None = None,
) -> RecoveryP106ReplayEvidence:
    """Replay-verify one retained P106 identity record against compatible P106 evidence."""
    if not isinstance(evidence, RecoveryP105ReplayIdentityStoreEvidence):
        raise ValueError("P106 stored P105 replay identity evidence has an incompatible type")
    if evidence.evidence_state != P106_EVIDENCE_STATE:
        raise ValueError("P106 stored P105 replay identity evidence state is incompatible")
    if evidence.automatic_control_allowed is not False:
        raise ValueError("P106 stored P105 replay identity evidence must not grant automatic-control authority")
    if any(getattr(evidence, flag, None) is not True for flag in _REQUIRED_P106_FLAGS):
        raise ValueError("P106 stored P105 replay identity verification flags are incomplete")

    values: dict[str, object] = {}
    for field, kind in _FIELDS:
        raw_value = getattr(evidence, field, None)
        values[field] = (
            _positive_int(raw_value, field=f"P106 {field}")
            if kind == "int"
            else _sha256(raw_value, field=f"P106 {field}")
        )

    stored_sha = _sha256(evidence.stored_payload_sha256, field="P106 stored payload SHA-256")
    stored_size = _positive_int(evidence.stored_payload_size_bytes, field="P106 stored payload size")
    selected = Path(evidence.destination_path if source_path is None else source_path)
    if not selected.name:
        raise ValueError("source path must identify a file")

    raw = selected.read_bytes()
    if len(raw) != stored_size:
        raise ValueError("retained P106 replay identity byte length mismatch")
    if hashlib.sha256(raw).hexdigest() != stored_sha:
        raise ValueError("retained P106 replay identity SHA-256 mismatch")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("retained P106 replay identity is not valid UTF-8") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("retained P106 replay identity is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("retained P106 replay identity must be a JSON object")
    if frozenset(payload) != _SCHEMA_KEYS:
        raise ValueError("retained P106 replay identity schema is incompatible")
    if _canonical(payload) != raw:
        raise ValueError("retained P106 replay identity is not strict canonical JSON")
    if payload.get("p105_evidence_state") != P105_EVIDENCE_STATE:
        raise ValueError("retained P106 replay identity embeds an incompatible P105 evidence state")

    for field, kind in _FIELDS:
        raw_value = payload.get(field)
        parsed = (
            _positive_int(raw_value, field=f"retained P106 {field}")
            if kind == "int"
            else _sha256(raw_value, field=f"retained P106 {field}")
        )
        if parsed != values[field]:
            raise ValueError(f"retained P106 replay identity disagrees on {field}")

    return RecoveryP106ReplayEvidence(
        **values,
        stored_payload_sha256=stored_sha,
        stored_payload_size_bytes=stored_size,
        source_path=str(selected),
        p106_evidence_state_verified=True,
        p106_verification_flags_verified=True,
        exact_payload_identity_verified=True,
        canonical_record_verified=True,
        semantic_agreement_verified=True,
    )
