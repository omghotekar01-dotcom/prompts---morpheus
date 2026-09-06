from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.recovery_p128 import EVIDENCE_STATE as P128_EVIDENCE_STATE, RecoveryP125P127CompositionEvidence
from app.recovery_p129 import EVIDENCE_STATE, SCHEMA, TRUTH_BOUNDARY, _FIELDS, canonicalize_p128_composition_receipt


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _evidence(**overrides: object) -> RecoveryP125P127CompositionEvidence:
    values: dict[str, object] = {}
    n = 29
    for field, kind in _FIELDS:
        if kind == "int":
            values[field] = n
            n += 19
        else:
            values[field] = _sha(field)
    values.update({"p125_contract_verified": True, "p127_contract_verified": True, "cross_evidence_identity_verified": True})
    values.update(overrides)
    return RecoveryP125P127CompositionEvidence(**values)


def test_p129_is_deterministic_canonical_and_non_authoritative() -> None:
    first = canonicalize_p128_composition_receipt(_evidence())
    second = canonicalize_p128_composition_receipt(_evidence())
    assert first == second
    assert first.evidence_state == EVIDENCE_STATE
    assert first.automatic_control_allowed is False
    assert first.p128_contract_verified and first.canonical_receipt_verified
    assert first.payload_sha256 == hashlib.sha256(first.payload).hexdigest()
    assert first.payload_size_bytes == len(first.payload)
    document = json.loads(first.payload)
    assert document["schema"] == SCHEMA
    assert document["p128_evidence_state"] == P128_EVIDENCE_STATE
    assert first.payload == json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


@pytest.mark.parametrize("flag", ["p125_contract_verified", "p127_contract_verified", "cross_evidence_identity_verified"])
def test_p129_rejects_weakened_p128_contract(flag: str) -> None:
    with pytest.raises(ValueError, match="verification flags"):
        canonicalize_p128_composition_receipt(replace(_evidence(), **{flag: False}))


def test_p129_rejects_state_and_authority_drift() -> None:
    with pytest.raises(ValueError, match="state"):
        canonicalize_p128_composition_receipt(replace(_evidence(), evidence_state="forged"))
    with pytest.raises(ValueError, match="automatic-control"):
        canonicalize_p128_composition_receipt(replace(_evidence(), automatic_control_allowed=True))


@pytest.mark.parametrize("field", [field for field, kind in _FIELDS if kind == "int"])
@pytest.mark.parametrize("bad", [False, 0, -1])
def test_p129_rejects_invalid_integer_identity_across_every_serialized_field(field: str, bad: object) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        canonicalize_p128_composition_receipt(replace(_evidence(), **{field: bad}))


@pytest.mark.parametrize("field", [field for field, kind in _FIELDS if kind == "sha"])
@pytest.mark.parametrize("bad", ["A" * 64, "f" * 63, "g" * 64])
def test_p129_rejects_invalid_sha_identity_across_every_serialized_field(field: str, bad: object) -> None:
    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        canonicalize_p128_composition_receipt(replace(_evidence(), **{field: bad}))


@pytest.mark.parametrize("field,kind", _FIELDS)
def test_p129_payload_identity_depends_on_every_semantic_field(field: str, kind: str) -> None:
    baseline = _evidence()
    replacement = getattr(baseline, field) + 1 if kind == "int" else _sha("changed-" + field)
    changed = replace(baseline, **{field: replacement})
    assert canonicalize_p128_composition_receipt(baseline).payload_sha256 != canonicalize_p128_composition_receipt(changed).payload_sha256


def test_p129_rejects_incompatible_type() -> None:
    with pytest.raises(ValueError, match="incompatible type"):
        canonicalize_p128_composition_receipt(object())  # type: ignore[arg-type]


def test_p129_truth_boundary_is_explicit() -> None:
    rendered = canonicalize_p128_composition_receipt(_evidence()).as_dict()
    assert rendered["automatic_control_allowed"] is False
    assert rendered["truth_boundary"] == TRUTH_BOUNDARY
    assert "does not authenticate" in TRUTH_BOUNDARY
    assert "freshness/latest/global/monotonic" in TRUTH_BOUNDARY
    assert "authorize startup or mutation" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark evidence" in TRUTH_BOUNDARY
    assert "novelty evidence" in TRUTH_BOUNDARY
    assert "automatic-control authority" in TRUTH_BOUNDARY
