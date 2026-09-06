"""Independently verify one stored P126 canonical P125-replay identity record.

P127 closes only the independent-read seam left explicit by P126. A caller supplies
P126 store evidence; this gate re-opens the selected local file, validates byte
identity, parses a strict JSON object without duplicate keys, enforces the exact
schema and canonical encoding, and compares every retained semantic field against
the supplied P126 evidence.

Successful verification proves local consistency with that supplied historical
evidence only. It does not authenticate either the evidence or filesystem and does
not establish freshness, monotonicity, startup authority, or automatic control.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import make_dataclass
from pathlib import Path

from .recovery_p125 import EVIDENCE_STATE as P125_EVIDENCE_STATE
from .recovery_p126 import (
    EVIDENCE_STATE as P126_EVIDENCE_STATE,
    RecoveryP125ReplayIdentityStoreEvidence,
    _FIELDS,
    _canonical,
    _positive_int,
    _sha256,
)

EVIDENCE_STATE = P126_EVIDENCE_STATE + "_INDEPENDENTLY_VERIFIED"
TRUTH_BOUNDARY = (
    "This gate proves only that one local stored P125 replay-identity file was independently read and matched the supplied compatible "
    "P126 store evidence by exact size, SHA-256, strict schema, canonical JSON bytes, retained semantic fields, and P125 evidence state. "
    "It does not authenticate the P126 evidence or filesystem, prove freshness/latest/global/monotonic head truth, prevent rollback/replay "
    "or coordinated evidence-and-file replacement, rerun P124/P125/P126 or dependencies, authorize startup or mutation, provide CAS, leases, "
    "fencing, TPM/HSM protection, remote witnessing, distributed consensus, HA, production readiness, benchmark evidence, novelty evidence, "
    "or automatic-control authority."
)

_PAYLOAD_FIELDS = tuple(field for field, _ in _FIELDS)
_EXPECTED_KEYS = frozenset((*_PAYLOAD_FIELDS, "p125_evidence_state"))


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"stored P125 replay identity contains duplicate key: {key}")
        result[key] = value
    return result


RecoveryP125ReplayIdentityVerificationEvidence = make_dataclass(
    "RecoveryP125ReplayIdentityVerificationEvidence",
    [
        *((field, int if kind == "int" else str) for field, kind in _FIELDS),
        ("stored_payload_sha256", str),
        ("stored_payload_size_bytes", int),
        ("source_path", str),
        ("exact_size_verified", bool),
        ("exact_sha256_verified", bool),
        ("strict_schema_verified", bool),
        ("canonical_encoding_verified", bool),
        ("retained_identity_verified", bool),
        ("p125_evidence_state_verified", bool),
        ("evidence_state", str, EVIDENCE_STATE),
        ("automatic_control_allowed", bool, False),
    ],
    frozen=True,
    namespace={"as_dict": lambda self: {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}},
)


def verify_stored_p125_replay_identity(
    evidence: RecoveryP125ReplayIdentityStoreEvidence,
    *,
    source_path: str | os.PathLike[str] | None = None,
) -> RecoveryP125ReplayIdentityVerificationEvidence:
    """Verify one stored P125 replay identity against compatible P126 evidence."""
    if not isinstance(evidence, RecoveryP125ReplayIdentityStoreEvidence):
        raise ValueError("P126 store evidence has an incompatible type")
    if evidence.evidence_state != P126_EVIDENCE_STATE:
        raise ValueError("P126 store evidence state is incompatible")
    if evidence.automatic_control_allowed is not False:
        raise ValueError("P126 store evidence must not grant automatic-control authority")
    for flag in (
        "p125_evidence_state_verified",
        "p125_verification_flags_verified",
        "exact_readback_verified",
    ):
        if getattr(evidence, flag, None) is not True:
            raise ValueError("P126 store evidence verification flags are incomplete")

    expected_sha = _sha256(evidence.stored_payload_sha256, field="P126 stored_payload_sha256")
    expected_size = _positive_int(evidence.stored_payload_size_bytes, field="P126 stored_payload_size_bytes")
    path = Path(evidence.destination_path if source_path is None else source_path)
    if not path.name:
        raise ValueError("source path must identify a file")

    try:
        encoded = path.read_bytes()
    except OSError as exc:
        raise ValueError("stored P125 replay identity could not be read") from exc

    if len(encoded) != expected_size:
        raise ValueError("stored P125 replay identity size mismatch")
    actual_sha = hashlib.sha256(encoded).hexdigest()
    if actual_sha != expected_sha:
        raise ValueError("stored P125 replay identity SHA-256 mismatch")

    try:
        decoded = encoded.decode("utf-8")
        payload = json.loads(decoded, object_pairs_hook=_strict_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("stored P125 replay identity is not strict UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("stored P125 replay identity must be a JSON object")
    if frozenset(payload) != _EXPECTED_KEYS:
        raise ValueError("stored P125 replay identity schema mismatch")
    if _canonical(payload) != encoded:
        raise ValueError("stored P125 replay identity is not canonically encoded")
    if payload.get("p125_evidence_state") != P125_EVIDENCE_STATE:
        raise ValueError("stored P125 replay identity has incompatible P125 evidence state")

    values: dict[str, object] = {}
    for field, kind in _FIELDS:
        raw = payload.get(field)
        value = (
            _positive_int(raw, field=f"stored {field}")
            if kind == "int"
            else _sha256(raw, field=f"stored {field}")
        )
        expected = getattr(evidence, field, None)
        if value != expected:
            raise ValueError(f"stored P125 replay identity field mismatch: {field}")
        values[field] = value

    return RecoveryP125ReplayIdentityVerificationEvidence(
        **values,
        stored_payload_sha256=actual_sha,
        stored_payload_size_bytes=len(encoded),
        source_path=str(path),
        exact_size_verified=True,
        exact_sha256_verified=True,
        strict_schema_verified=True,
        canonical_encoding_verified=True,
        retained_identity_verified=True,
        p125_evidence_state_verified=True,
    )
