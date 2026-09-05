from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from app.recovery_p108 import EVIDENCE_STATE as P108_EVIDENCE_STATE
from app.recovery_p110 import RecoveryP109ReplayEvidence
from app.recovery_p112 import EVIDENCE_STATE as P112_EVIDENCE_STATE, RecoveryP111ReplayEvidence
from app.recovery_p113 import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    _FIELDS,
    RecoveryP110P112CompositionEvidence,
    bind_p110_replay_to_p112_retained_identity,
)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _shared() -> dict[str, object]:
    values: dict[str, object] = {}
    next_int = 19
    for field, kind in _FIELDS:
        if kind == "int":
            values[field] = next_int
            next_int += 23
        else:
            values[field] = _sha(field)
    return values


def _p110(**overrides: object) -> RecoveryP109ReplayEvidence:
    kwargs = {
        **_shared(),
        "expected_payload_identity_verified": True,
        "canonical_receipt_verified": True,
        "dependency_state_verified": True,
        "p105_p107_composition_binding_recomputed_verified": True,
        "p108_evidence_state": P108_EVIDENCE_STATE,
    }
    kwargs.update(overrides)
    return RecoveryP109ReplayEvidence(**kwargs)


def _p112(**overrides: object) -> RecoveryP111ReplayEvidence:
    kwargs = {
        **_shared(),
        "stored_payload_sha256": _sha("retained-p111-record"),
        "stored_payload_size_bytes": 911,
        "source_path": "evidence/p111.json",
        "p111_evidence_state_verified": True,
        "p111_verification_flags_verified": True,
        "exact_payload_identity_verified": True,
        "canonical_record_verified": True,
        "semantic_agreement_verified": True,
    }
    kwargs.update(overrides)
    return RecoveryP111ReplayEvidence(**kwargs)


def test_p113_composes_deterministically_without_authority() -> None:
    first = bind_p110_replay_to_p112_retained_identity(_p110(), _p112())
    second = bind_p110_replay_to_p112_retained_identity(_p110(), _p112())

    assert isinstance(first, RecoveryP110P112CompositionEvidence)
    assert first == second
    assert first.evidence_state == EVIDENCE_STATE
    assert first.automatic_control_allowed is False
    assert first.p110_contract_verified is True
    assert first.p112_contract_verified is True
    assert first.cross_evidence_identity_verified is True
    assert first.retained_p111_record_payload_sha256 == _sha("retained-p111-record")
    assert first.retained_p111_record_payload_size_bytes == 911
    assert len(first.p110_p112_composition_binding_sha256) == 64


@pytest.mark.parametrize("field,kind", _FIELDS)
def test_p113_rejects_every_shared_identity_mismatch(field: str, kind: str) -> None:
    baseline = _p112()
    replacement = getattr(baseline, field) + 1 if kind == "int" else _sha(f"mismatch-{field}")
    with pytest.raises(ValueError, match="disagrees"):
        bind_p110_replay_to_p112_retained_identity(_p110(), replace(baseline, **{field: replacement}))


@pytest.mark.parametrize(
    "flag",
    [
        "expected_payload_identity_verified",
        "canonical_receipt_verified",
        "dependency_state_verified",
        "p105_p107_composition_binding_recomputed_verified",
    ],
)
def test_p113_rejects_weakened_p110_contract(flag: str) -> None:
    with pytest.raises(ValueError, match="P110 verification contract"):
        bind_p110_replay_to_p112_retained_identity(replace(_p110(), **{flag: False}), _p112())


@pytest.mark.parametrize(
    "flag",
    [
        "p111_evidence_state_verified",
        "p111_verification_flags_verified",
        "exact_payload_identity_verified",
        "canonical_record_verified",
        "semantic_agreement_verified",
    ],
)
def test_p113_rejects_weakened_p112_contract(flag: str) -> None:
    with pytest.raises(ValueError, match="P112 verification contract"):
        bind_p110_replay_to_p112_retained_identity(_p110(), replace(_p112(), **{flag: False}))


def test_p113_rejects_dependency_state_drift() -> None:
    with pytest.raises(ValueError, match="P110 evidence state"):
        bind_p110_replay_to_p112_retained_identity(replace(_p110(), evidence_state="drift"), _p112())
    with pytest.raises(ValueError, match="embedded P108"):
        bind_p110_replay_to_p112_retained_identity(replace(_p110(), p108_evidence_state="drift"), _p112())
    with pytest.raises(ValueError, match="P112 evidence state"):
        bind_p110_replay_to_p112_retained_identity(_p110(), replace(_p112(), evidence_state="drift"))


def test_p113_rejects_automatic_control_escalation() -> None:
    with pytest.raises(ValueError, match="P110 evidence must not grant"):
        bind_p110_replay_to_p112_retained_identity(replace(_p110(), automatic_control_allowed=True), _p112())
    with pytest.raises(ValueError, match="P112 evidence must not grant"):
        bind_p110_replay_to_p112_retained_identity(_p110(), replace(_p112(), automatic_control_allowed=True))


@pytest.mark.parametrize("field", [field for field, kind in _FIELDS if kind == "int"])
@pytest.mark.parametrize("bad", [True, 0, -1])
def test_p113_rejects_invalid_integer_identity_across_shared_fields(field: str, bad: object) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        bind_p110_replay_to_p112_retained_identity(replace(_p110(), **{field: bad}), _p112())


@pytest.mark.parametrize("field", [field for field, kind in _FIELDS if kind == "sha"])
@pytest.mark.parametrize("bad", ["A" * 64, "f" * 63, "g" * 64])
def test_p113_rejects_malformed_sha_identity_across_shared_fields(field: str, bad: object) -> None:
    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        bind_p110_replay_to_p112_retained_identity(replace(_p110(), **{field: bad}), _p112())


@pytest.mark.parametrize("bad", [True, 0, -9])
def test_p113_rejects_invalid_retained_record_size(bad: object) -> None:
    with pytest.raises(ValueError, match="retained P111 record size"):
        bind_p110_replay_to_p112_retained_identity(_p110(), replace(_p112(), stored_payload_size_bytes=bad))


def test_p113_rejects_invalid_retained_record_sha() -> None:
    with pytest.raises(ValueError, match="retained P111 record SHA-256"):
        bind_p110_replay_to_p112_retained_identity(_p110(), replace(_p112(), stored_payload_sha256="bad"))


def test_p113_binding_commits_to_retained_record_identity() -> None:
    baseline = bind_p110_replay_to_p112_retained_identity(_p110(), _p112())
    changed_sha = bind_p110_replay_to_p112_retained_identity(
        _p110(), replace(_p112(), stored_payload_sha256=_sha("other-record"))
    )
    changed_size = bind_p110_replay_to_p112_retained_identity(
        _p110(), replace(_p112(), stored_payload_size_bytes=912)
    )
    assert baseline.p110_p112_composition_binding_sha256 != changed_sha.p110_p112_composition_binding_sha256
    assert baseline.p110_p112_composition_binding_sha256 != changed_size.p110_p112_composition_binding_sha256


def test_p113_binding_commits_to_dependency_evidence_states(monkeypatch: pytest.MonkeyPatch) -> None:
    baseline = bind_p110_replay_to_p112_retained_identity(_p110(), _p112())
    monkeypatch.setattr("app.recovery_p113.P112_EVIDENCE_STATE", P112_EVIDENCE_STATE + "_ALT")
    altered_retained = replace(_p112(), evidence_state=P112_EVIDENCE_STATE + "_ALT")
    altered = bind_p110_replay_to_p112_retained_identity(_p110(), altered_retained)
    assert baseline.p110_p112_composition_binding_sha256 != altered.p110_p112_composition_binding_sha256


@pytest.mark.parametrize("left,right", [(object(), None), (None, object()), ("bad", "bad")])
def test_p113_rejects_incompatible_types(left: object, right: object) -> None:
    with pytest.raises(ValueError, match="incompatible type"):
        bind_p110_replay_to_p112_retained_identity(left, right)  # type: ignore[arg-type]


def test_p113_truth_boundary_is_explicit_and_non_scientific_overclaiming() -> None:
    evidence = bind_p110_replay_to_p112_retained_identity(_p110(), _p112())
    exported = evidence.as_dict()

    assert exported["truth_boundary"] == TRUTH_BOUNDARY
    assert "does not authenticate" in TRUTH_BOUNDARY
    assert "freshness/latest/global/monotonic" in TRUTH_BOUNDARY
    assert "coordinated rollback/replay" in TRUTH_BOUNDARY
    assert "authorize startup or mutation" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark evidence" in TRUTH_BOUNDARY
    assert "novelty evidence" in TRUTH_BOUNDARY
    assert "automatic-control authority" in TRUTH_BOUNDARY
    assert evidence.automatic_control_allowed is False
