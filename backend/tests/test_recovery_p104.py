from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.recovery_p103 import RecoveryP100P102CompositionEvidence
from app.recovery_p104 import (
    EVIDENCE_STATE,
    SCHEMA,
    TRUTH_BOUNDARY,
    _FIELDS,
    RecoveryP103CompositionReceiptEvidence,
    canonicalize_p103_composition_receipt,
)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _p103(**overrides: object) -> RecoveryP100P102CompositionEvidence:
    values: dict[str, object] = {}
    next_int = 7
    for field, kind in _FIELDS:
        if kind == "int":
            values[field] = next_int
            next_int += 11
        else:
            values[field] = _sha(field)
    values.update(
        {
            "p100_contract_verified": True,
            "p102_contract_verified": True,
            "cross_evidence_identity_verified": True,
        }
    )
    values.update(overrides)
    return RecoveryP100P102CompositionEvidence(**values)


def test_p104_is_deterministic_canonical_and_non_authoritative() -> None:
    first = canonicalize_p103_composition_receipt(_p103())
    second = canonicalize_p103_composition_receipt(_p103())

    assert isinstance(first, RecoveryP103CompositionReceiptEvidence)
    assert first == second
    assert first.evidence_state == EVIDENCE_STATE
    assert first.automatic_control_allowed is False
    assert first.p103_contract_verified is True
    assert first.canonical_receipt_verified is True
    assert first.payload_size_bytes == len(first.payload)
    assert first.payload_sha256 == hashlib.sha256(first.payload).hexdigest()

    decoded = json.loads(first.payload)
    assert decoded["schema"] == SCHEMA
    assert first.payload == json.dumps(decoded, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


@pytest.mark.parametrize("flag", ["p100_contract_verified", "p102_contract_verified", "cross_evidence_identity_verified"])
def test_p104_rejects_weakened_p103_contract(flag: str) -> None:
    with pytest.raises(ValueError, match="verification flags"):
        canonicalize_p103_composition_receipt(replace(_p103(), **{flag: False}))


def test_p104_rejects_state_drift_and_authority_escalation() -> None:
    with pytest.raises(ValueError, match="evidence state"):
        canonicalize_p103_composition_receipt(replace(_p103(), evidence_state="drift"))
    with pytest.raises(ValueError, match="must not grant"):
        canonicalize_p103_composition_receipt(replace(_p103(), automatic_control_allowed=True))


@pytest.mark.parametrize("bad", [True, 0, -1])
def test_p104_rejects_invalid_positive_integer_identity(bad: object) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        canonicalize_p103_composition_receipt(replace(_p103(), sequence=bad))


@pytest.mark.parametrize("bad", ["A" * 64, "f" * 63, "g" * 64, 123])
def test_p104_rejects_malformed_sha_identity(bad: object) -> None:
    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        canonicalize_p103_composition_receipt(replace(_p103(), lineage_sha256=bad))


@pytest.mark.parametrize("field,kind", _FIELDS)
def test_p104_payload_identity_commits_to_every_serialized_semantic_field(field: str, kind: str) -> None:
    baseline = canonicalize_p103_composition_receipt(_p103())
    current = getattr(_p103(), field)
    changed = current + 1 if kind == "int" else _sha(f"changed-{field}")
    altered = canonicalize_p103_composition_receipt(replace(_p103(), **{field: changed}))

    assert baseline.payload != altered.payload
    assert baseline.payload_sha256 != altered.payload_sha256


@pytest.mark.parametrize("bad", [object(), None, "bad", {}])
def test_p104_rejects_incompatible_type(bad: object) -> None:
    with pytest.raises(ValueError, match="incompatible type"):
        canonicalize_p103_composition_receipt(bad)  # type: ignore[arg-type]


def test_p104_truth_boundary_is_explicit_and_non_overclaiming() -> None:
    evidence = canonicalize_p103_composition_receipt(_p103())
    exported = evidence.as_dict()

    assert exported["truth_boundary"] == TRUTH_BOUNDARY
    assert "does not authenticate" in TRUTH_BOUNDARY
    assert "freshness/latest/global/monotonic" in TRUTH_BOUNDARY
    assert "coordinated rollback" in TRUTH_BOUNDARY
    assert "authorize startup or mutation" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark evidence" in TRUTH_BOUNDARY
    assert "novelty evidence" in TRUTH_BOUNDARY
    assert "automatic-control authority" in TRUTH_BOUNDARY
    assert evidence.automatic_control_allowed is False
