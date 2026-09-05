from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.recovery_p108 import EVIDENCE_STATE as P108_EVIDENCE_STATE, RecoveryP105P107CompositionEvidence
from app.recovery_p109 import EVIDENCE_STATE, SCHEMA, TRUTH_BOUNDARY, _FIELDS, canonicalize_p108_composition_receipt


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _evidence(**overrides: object) -> RecoveryP105P107CompositionEvidence:
    values: dict[str, object] = {}
    n = 11
    for field, kind in _FIELDS:
        if kind == "int":
            values[field] = n
            n += 7
        else:
            values[field] = _sha(field)
    values.update({"p105_contract_verified": True, "p107_contract_verified": True, "cross_evidence_identity_verified": True})
    values.update(overrides)
    return RecoveryP105P107CompositionEvidence(**values)


def test_p109_is_deterministic_canonical_and_non_authoritative() -> None:
    first = canonicalize_p108_composition_receipt(_evidence())
    second = canonicalize_p108_composition_receipt(_evidence())
    assert first == second
    assert first.evidence_state == EVIDENCE_STATE
    assert first.automatic_control_allowed is False
    assert first.p108_contract_verified and first.canonical_receipt_verified
    assert first.payload_sha256 == hashlib.sha256(first.payload).hexdigest()
    assert first.payload_size_bytes == len(first.payload)
    document = json.loads(first.payload)
    assert document["schema"] == SCHEMA
    assert document["p108_evidence_state"] == P108_EVIDENCE_STATE
    assert first.payload == json.dumps(document, sort_keys=True, separators=(",", ","), allow_nan=False).encode()


@pytest.mark.parametrize("flag", ["p105_contract_verified", "p107_contract_verified", "cross_evidence_identity_verified"])
def test_p109_rejects_weakened_p108_contract(flag: str) -> None:
    with pytest.raises(ValueError, match="verification flags"):
        canonicalize_p108_composition_receipt(replace(_evidence(), **{flag: False}))


def test_p109_rejects_state_and_authority_drift() -> None:
    with pytest.raises(ValueError, match="state"):
        canonicalize_p108_composition_receipt(replace(_evidence(), evidence_state="forged"))
    with pytest.raises(ValueError, match="automatic-control"):
        canonicalize_p108_composition_receipt(replace(_evidence(), automatic_control_allowed=True))


@pytest.mark.parametrize("field,kind", _FIELDS)
def test_p109_validates_every_serialized_identity(field: str, kind: str) -> None:
    bad = False if kind == "int" else "A" * 64
    with pytest.raises(ValueError):
        canonicalize_p108_composition_receipt(replace(_evidence(), **{field: bad}))


@pytest.mark.parametrize("field,kind", _FIELDS)
def test_p109_payload_identity_depends_on_every_semantic_field(field: str, kind: str) -> None:
    baseline = _evidence()
    replacement = getattr(baseline, field) + 1 if kind == "int" else _sha("changed-" + field)
    changed = replace(baseline, **{field: replacement})
    assert canonicalize_p108_composition_receipt(baseline).payload_sha256 != canonicalize_p108_composition_receipt(changed).payload_sha256


def test_p109_rejects_incompatible_type() -> None:
    with pytest.raises(ValueError, match="incompatible type"):
        canonicalize_p108_composition_receipt(object())  # type: ignore[arg-type]


def test_p109_truth_boundary_is_explicit() -> None:
    assert "does not authenticate" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark evidence" in TRUTH_BOUNDARY
    assert "novelty evidence" in TRUTH_BOUNDARY
    assert "automatic-control authority" in TRUTH_BOUNDARY
