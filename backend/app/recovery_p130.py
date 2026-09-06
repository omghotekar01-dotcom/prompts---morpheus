"""Independently verify canonical P129 composition-receipt bytes.

P130 closes only the byte-transport seam left explicit by P129. A caller supplies
compatible P129 evidence plus independently obtained receipt bytes. This gate checks
exact size and SHA-256, strict UTF-8 JSON without duplicate keys, exact schema,
canonical encoding, every retained semantic field, and the bound P128 evidence state.

Successful verification proves consistency with the supplied P129 evidence only. It
neither authenticates that evidence nor establishes freshness, startup authority, or
automatic-control authority.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .recovery_p128 import EVIDENCE_STATE as P128_EVIDENCE_STATE
from .recovery_p129 import (
    EVIDENCE_STATE as P129_EVIDENCE_STATE,
    SCHEMA as P129_SCHEMA,
    _FIELDS as P129_FIELDS,
    RecoveryP128CompositionReceiptEvidence,
)

EVIDENCE_STATE = P129_EVIDENCE_STATE + "_INDEPENDENTLY_VERIFIED"
TRUTH_BOUNDARY = (
    "This read-only gate proves only that independently supplied P129 receipt bytes matched compatible supplied P129 evidence by exact "
    "size, SHA-256, strict schema, canonical JSON encoding, retained semantic fields, and P128 evidence state. It does not authenticate "
    "the P129 evidence or receipt source, prove freshness/latest/global/monotonic head truth, prevent replay or coordinated rollback, rerun "
    "P125/P127/P128/P129 or dependencies, authorize startup or mutation, provide CAS, leases, fencing, TPM/HSM protection, remote witnessing, "
    "distributed consensus, HA, production readiness, benchmark evidence, novelty evidence, or automatic-control authority."
)

_PAYLOAD_FIELDS = tuple(field for field, _ in P129_FIELDS)
_EXPECTED_KEYS = frozenset(("schema", *_PAYLOAD_FIELDS, "p128_evidence_state"))


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"P129 receipt contains duplicate key: {key}")
        result[key] = value
    return result


def _positive_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _sha256(value: object, *, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or value.lower() != value or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{field} must be 64 lowercase hexadecimal characters")
    return value


def _canonical(document: dict[str, object]) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


@dataclass(frozen=True)
class RecoveryP129ReceiptVerificationEvidence:
    receipt_payload_sha256: str
    receipt_payload_size_bytes: int
    exact_size_verified: bool
    exact_sha256_verified: bool
    strict_schema_verified: bool
    canonical_encoding_verified: bool
    retained_identity_verified: bool
    p128_evidence_state_verified: bool
    p129_contract_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def verify_p129_composition_receipt(
    evidence: RecoveryP128CompositionReceiptEvidence,
    payload: bytes,
) -> RecoveryP129ReceiptVerificationEvidence:
    """Verify independently supplied P129 receipt bytes against compatible evidence."""
    if not isinstance(evidence, RecoveryP128CompositionReceiptEvidence):
        raise ValueError("P129 receipt evidence has an incompatible type")
    if evidence.evidence_state != P129_EVIDENCE_STATE:
        raise ValueError("P129 receipt evidence state is incompatible")
    if evidence.automatic_control_allowed is not False:
        raise ValueError("P129 receipt evidence must not grant automatic-control authority")
    if evidence.p128_contract_verified is not True or evidence.canonical_receipt_verified is not True:
        raise ValueError("P129 receipt evidence verification flags are incomplete")
    if not isinstance(payload, bytes):
        raise ValueError("P129 receipt payload must be bytes")

    expected_size = _positive_int(evidence.payload_size_bytes, field="P129 payload_size_bytes")
    expected_sha = _sha256(evidence.payload_sha256, field="P129 payload_sha256")
    if len(payload) != expected_size:
        raise ValueError("P129 receipt payload size mismatch")
    actual_sha = hashlib.sha256(payload).hexdigest()
    if actual_sha != expected_sha:
        raise ValueError("P129 receipt payload SHA-256 mismatch")
    if evidence.payload != payload:
        raise ValueError("P129 receipt payload bytes mismatch")

    try:
        decoded = payload.decode("utf-8")
        document = json.loads(decoded, object_pairs_hook=_strict_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("P129 receipt payload is not strict UTF-8 JSON") from exc
    if not isinstance(document, dict):
        raise ValueError("P129 receipt payload must be a JSON object")
    if frozenset(document) != _EXPECTED_KEYS:
        raise ValueError("P129 receipt payload schema mismatch")
    if document.get("schema") != P129_SCHEMA:
        raise ValueError("P129 receipt schema identifier is incompatible")
    if _canonical(document) != payload:
        raise ValueError("P129 receipt payload is not canonically encoded")
    if document.get("p128_evidence_state") != P128_EVIDENCE_STATE:
        raise ValueError("P129 receipt has incompatible P128 evidence state")

    for field, kind in P129_FIELDS:
        raw = document.get(field)
        if kind == "int":
            _positive_int(raw, field=f"P129 receipt {field}")
        else:
            _sha256(raw, field=f"P129 receipt {field}")

    return RecoveryP129ReceiptVerificationEvidence(
        receipt_payload_sha256=actual_sha,
        receipt_payload_size_bytes=len(payload),
        exact_size_verified=True,
        exact_sha256_verified=True,
        strict_schema_verified=True,
        canonical_encoding_verified=True,
        retained_identity_verified=True,
        p128_evidence_state_verified=True,
        p129_contract_verified=True,
    )
