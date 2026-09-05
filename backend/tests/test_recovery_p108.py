from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from app.recovery_p103 import EVIDENCE_STATE as P103_EVIDENCE_STATE
from app.recovery_p105 import RecoveryP104ReplayEvidence
from app.recovery_p107 import EVIDENCE_STATE as P107_EVIDENCE_STATE, RecoveryP106ReplayEvidence
from app.recovery_p108 import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    _FIELDS,
    RecoveryP105P107CompositionEvidence,
    bind_p105_replay_to_p107_retained_identity,
)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _shared() -> dict[str, object]:
    values: dict[str, object] = {}
    next_int = 13
    for field, kind in _FIELDS:
        if kind == "int":
            values[field] = next_int
            next_int += 17
        else:
            values[field] = _sha(field)
    return values


def _p105(**overrides: object) -> RecoveryP104ReplayEvidence:
    kwargs = {
        **_shared(),
        "expected_payload_identity_verified": True,
        "canonical_receipt_verified": True,
        "dependency_state_verified": True,
        "p100_p102_composition_binding_recomputed_verified": True,
        "p103_evidence_state": P103_EVIDENCE_STATE,
    }
    kwargs.update(overrides)
    return RecoveryP104ReplayEvidence(**kwargs)


def _p107(**overrides: object) -> RecoveryP106ReplayEvidence:
    kwargs = {
        **_shared(),
        "stored_payload_sha256": _sha("retained-p106-record"),
        "stored_payload_size_bytes": 733,
        "source_path": "evidence/p106.json",
        "p106_evidence_state_verified": True,
        "p106_verification_flags_verified": True,
        "exact_payload_identity_verified": True,
        "canonical_record_verified": True,
        "semantic_agreement_verified": True,
    }
    kwargs.update(overrides)
    return RecoveryP106ReplayEvidence(**kwargs)


def test_p108_composes_deterministically_without_authority() -> None:
    first = bind_p105_replay_to_p107_retained_identity(_p105(), _p107())
    second = bind_p105_replay_to_p107_retained_identity(_p105(), _p107())

    assert isinstance(first, RecoveryP105P107CompositionEvidence)
    assert first == second
    assert first.evidence_state == EVIDENCE_STATE
    assert first.automatic_control_allowed is False
    assert first.p105_contract_verified is True
    assert first.p107_contract_verified is True
    assert first.cross_evidence_identity_verified is True
    assert first.retained_p106_record_payload_sha256 == _sha("retained-p106-record")
    assert first.retained_p106_record_payload_size_bytes == 733
    assert len(first.p105_p107_composition_binding_sha256) == 64


@pytest.mark.parametrize("field,kind", _FIELDS)
def test_p108_rejects_every_shared_identity_mismatch(field: str, kind: str) -> None:
    baseline = _p107()
    replacement = getattr(baseline, field) + 1 if kind == "int" else _sha(f"mismatch-{field}")
    with pytest.raises(ValueError, match="disagrees"):
        bind_p105_replay_to_p107_retained_identity(_p105(), replace(baseline, **{field: replacement}))


@pytest.mark.parametrize(
    "flag",
    [
        "expected_payload_identity_verified",
        "canonical_receipt_verified",
        "dependency_state_verified",
        "p100_p102_composition_binding_recomputed_verified",
    ],
)
def test_p108_rejects_weakened_p105_contract(flag: str) -> None:
    with pytest.raises(ValueError, match="P105 verification contract"):
        bind_p105_replay_to_p107_retained_identity(replace(_p105(), **{flag: False}), _p107())


@pytest.mark.parametrize(
    "flag",
    [
        "p106_evidence_state_verified",
        "p106_verification_flags_verified",
        "exact_payload_identity_verified",
        "canonical_record_verified",
        "semantic_agreement_verified",
    ],
)
def test_p108_rejects_weakened_p107_contract(flag: str) -> None:
    with pytest.raises(ValueError, match="P107 verification contract"):
        bind_p105_replay_to_p107_retained_identity(_p105(), replace(_p107(), **{flag: False}))


def test_p108_rejects_dependency_state_drift() -> None:
    with pytest.raises(ValueError, match="P105 evidence state"):
        bind_p105_replay_to_p107_retained_identity(replace(_p105(), evidence_state="drift"), _p107())
    with pytest.raises(ValueError, match="embedded P103"):
        bind_p105_replay_to_p107_retained_identity(replace(_p105(), p103_evidence_state="drift"), _p107())
    with pytest.raises(ValueError, match="P107 evidence state"):
        bind_p105_replay_to_p107_retained_identity(_p105(), replace(_p107(), evidence_state="drift"))


def test_p108_rejects_automatic_control_escalation() -> None:
    with pytest.raises(ValueError, match="P105 evidence must not grant"):
        bind_p105_replay_to_p107_retained_identity(replace(_p105(), automatic_control_allowed=True), _p107())
    with pytest.raises(ValueError, match="P107 evidence must not grant"):
        bind_p105_replay_to_p107_retained_identity(_p105(), replace(_p107(), automatic_control_allowed=True))


@pytest.mark.parametrize("bad", [True, 0, -1])
def test_p108_rejects_invalid_positive_integer_identity(bad: object) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        bind_p105_replay_to_p107_retained_identity(replace(_p105(), sequence=bad), _p107())


@pytest.mark.parametrize("bad", ["A" * 64, "f" * 63, "g" * 64, 123])
def test_p108_rejects_malformed_sha_identity(bad: object) -> None:
    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        bind_p105_replay_to_p107_retained_identity(replace(_p105(), lineage_sha256=bad), _p107())


@pytest.mark.parametrize("bad", [True, 0, -9])
def test_p108_rejects_invalid_retained_record_size(bad: object) -> None:
    with pytest.raises(ValueError, match="retained P106 record size"):
        bind_p105_replay_to_p107_retained_identity(_p105(), replace(_p107(), stored_payload_size_bytes=bad))


def test_p108_rejects_invalid_retained_record_sha() -> None:
    with pytest.raises(ValueError, match="retained P106 record SHA-256"):
        bind_p105_replay_to_p107_retained_identity(_p105(), replace(_p107(), stored_payload_sha256="bad"))


def test_p108_binding_commits_to_retained_record_identity() -> None:
    baseline = bind_p105_replay_to_p107_retained_identity(_p105(), _p107())
    changed_sha = bind_p105_replay_to_p107_retained_identity(
        _p105(), replace(_p107(), stored_payload_sha256=_sha("other-record"))
    )
    changed_size = bind_p105_replay_to_p107_retained_identity(
        _p105(), replace(_p107(), stored_payload_size_bytes=734)
    )
    assert baseline.p105_p107_composition_binding_sha256 != changed_sha.p105_p107_composition_binding_sha256
    assert baseline.p105_p107_composition_binding_sha256 != changed_size.p105_p107_composition_binding_sha256


def test_p108_binding_commits_to_dependency_evidence_states(monkeypatch: pytest.MonkeyPatch) -> None:
    baseline = bind_p105_replay_to_p107_retained_identity(_p105(), _p107())
    monkeypatch.setattr("app.recovery_p108.P107_EVIDENCE_STATE", P107_EVIDENCE_STATE + "_ALT")
    altered_retained = replace(_p107(), evidence_state=P107_EVIDENCE_STATE + "_ALT")
    altered = bind_p105_replay_to_p107_retained_identity(_p105(), altered_retained)
    assert baseline.p105_p107_composition_binding_sha256 != altered.p105_p107_composition_binding_sha256


@pytest.mark.parametrize("left,right", [(object(), None), (None, object()), ("bad", "bad")])
def test_p108_rejects_incompatible_types(left: object, right: object) -> None:
    with pytest.raises(ValueError, match="incompatible type"):
        bind_p105_replay_to_p107_retained_identity(left, right)  # type: ignore[arg-type]


def test_p108_truth_boundary_is_explicit_and_non_scientific_overclaiming() -> None:
    evidence = bind_p105_replay_to_p107_retained_identity(_p105(), _p107())
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
