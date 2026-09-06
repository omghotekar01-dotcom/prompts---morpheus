"""Independently verify one stored P131 canonical P130-receipt identity record.

P132 closes only the independent-read seam left explicit by P131. A caller supplies
P131 store evidence; this gate re-opens the selected local file, validates byte
identity, parses a strict JSON object without duplicate keys, enforces the exact
schema and canonical encoding, and compares every retained semantic field against
the supplied P131 evidence.

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

from .recovery_p130 import EVIDENCE_STATE as P130_EVIDENCE_STATE
from .recovery_p131 import (
    EVIDENCE_STATE as P131_EVIDENCE_STATE,
    RecoveryP130ReceiptIdentityStoreEvidence,
    _FIELDS,
    _canonical,
    _positive_int,
    _sha256,
)

EVIDENCE_STATE = P131_EVIDENCE_STATE + "_INDEPENDENTLY_VERIFIED"
TRUTH_BOUNDARY = (
    "This gate proves only that one local stored P130 receipt-identity file was independently read and matched the supplied compatible "
    "P131 store evidence by exact size, SHA-256, strict schema, canonical JSON bytes, retained semantic fields, and P130 evidence state. "
    "It does not authenticate the P131 evidence or filesystem, prove freshness/latest/global/monotonic head truth, prevent rollback/replay "
    "or coordinated evidence-and-file replacement, rerun P129/P130/P131 or dependencies, authorize startup or mutation, provide CAS, leases, "
    "fencing, TPM/HSM protection, remote witnessing, distributed consensus, HA, production readiness, benchmark evidence, novelty evidence, "
    "or automatic-control authority."
)

_PAYLOAD_FIELDS = tuple(field for field, _ in _FIELDS)
_EXPECTED_KEYS = frozenset((*_PAYLOAD_FIELDS, "p130_evidence_state"))


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"stored P130 receipt identity contains duplicate key: {key}")
        result[key] = value
    return result


RecoveryP130ReceiptIdentityVerificationEvidence = make_dataclass(
    "RecoveryP130ReceiptIdentityVerificationEvidence",
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
        ("p130_evidence_state_verified", bool),
        ("evidence_state", str, EVIDENCE_STATE),
        ("automatic_control_allowed", bool, False),
    ],
    frozen=True,
    namespace={"as_dict": lambda self: {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}},
)


def verify_stored_p130_receipt_identity(
    evidence: RecoveryP130ReceiptIdentityStoreEvidence,
    *,
    source_path: str | os.PathLike[str] | None = None,
) -> RecoveryP130ReceiptIdentityVerificationEvidence:
    """Verify one stored P130 receipt identity against compatible P131 evidence."""
    if not isinstance(evidence, RecoveryP130ReceiptIdentityStoreEvidence):
        raise ValueError("P131 store evidence has an incompatible type")
    if evidence.evidence_state != P131_EVIDENCE_STATE:
        raise ValueError("P131 store evidence state is incompatible")
    if evidence.automatic_control_allowed is not False:
        raise ValueError("P131 store evidence must not grant automatic-control authority")
    for flag in (
        "p130_evidence_state_verified",
        "p130_verification_flags_verified",
        "exact_readback_verified",
    ):
        if getattr(evidence, flag, None) is not True:
            raise ValueError("P131 store evidence verification flags are incomplete")

    expected_sha = _sha256(evidence.stored_payload_sha256, field="P131 stored_payload_sha256")
    expected_size = _positive_int(evidence.stored_payload_size_bytes, field="P131 stored_payload_size_bytes")
    path = Path(evidence.destination_path if source_path is None else source_path)
    if not path.name:
        raise ValueError("source path must identify a file")

    try:
        encoded = path.read_bytes()
    except OSError as exc:
        raise ValueError("stored P130 receipt identity could not be read") from exc

    if len(encoded) != expected_size:
        raise ValueError("stored P130 receipt identity size mismatch")
    actual_sha = hashlib.sha256(encoded).hexdigest()
    if actual_sha != expected_sha:
        raise ValueError("stored P130 receipt identity SHA-256 mismatch")

    try:
        decoded = encoded.decode("utf-8")
        payload = json.loads(decoded, object_pairs_hook=_strict_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("stored P130 receipt identity is not strict UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("stored P130 receipt identity must be a JSON object")
    if frozenset(payload) != _EXPECTED_KEYS:
        raise ValueError("stored P130 receipt identity schema mismatch")
    if _canonical(payload) != encoded:
        raise ValueError("stored P130 receipt identity is not canonically encoded")
    if payload.get("p130_evidence_state") != P130_EVIDENCE_STATE:
        raise ValueError("stored P130 receipt identity has incompatible P130 evidence state")

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
            raise ValueError(f"stored P130 receipt identity field mismatch: {field}")
        values[field] = value

    return RecoveryP130ReceiptIdentityVerificationEvidence(
        **values,
        stored_payload_sha256=actual_sha,
        stored_payload_size_bytes=len(encoded),
        source_path=str(path),
        exact_size_verified=True,
        exact_sha256_verified=True,
        strict_schema_verified=True,
        canonical_encoding_verified=True,
        retained_identity_verified=True,
        p130_evidence_state_verified=True,
    )
