from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from app.recovery_p113 import EVIDENCE_STATE as P113_EVIDENCE_STATE
from app.recovery_p115 import RecoveryP114ReplayEvidence
from app.recovery_p117 import EVIDENCE_STATE as P117_EVIDENCE_STATE, RecoveryP116ReplayEvidence
from app.recovery_p118 import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    _FIELDS,
    RecoveryP115P117CompositionEvidence,
    bind_p115_replay_to_p117_retained_identity,
)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _shared() -> dict[str, object]:
    values: dict[str, object] = {}
    next_int = 31
    for field, kind in _FIELDS:
        if kind == "int":
            values[field] = next_int
            next_int += 29
        else:
            values[field] = _sha(field)
    return values


def _p115(**overrides: object) -> RecoveryP114ReplayEvidence:
    kwargs = {
        **_shared(),
        "expected_payload_identity_verified": True,
        "canonical_receipt_verified": True,
        "dependency_state_verified": True,
        "p110_p112_composition_binding_recomputed_verified": True,
        "p113_evidence_state": P113_EVIDENCE_STATE,
    }
    kwargs.update(overrides)
    return RecoveryP114ReplayEvidence(**kwargs)


def _p117(**overrides: object) -> RecoveryP116ReplayEvidence:
    kwargs = {
        **_shared(),
        "stored_payload_sha256": _sha("retained-p116-record"),
        "stored_payload_size_bytes": 1217,
        "source_path": "evidence/p116.json",
        "p116_evidence_state_verified": True,
        "p116_verification_flags_verified": True,
        "exact_payload_identity_verified": True,
        "canonical_record_verified": True,
        "semantic_agreement_verified": True,
    }
    kwargs.update(overrides)
    return RecoveryP116ReplayEvidence(**kwargs)


def test_p118_composes_deterministically_without_authority() -> None:
    first = bind_p115_replay_to_p117_retained_identity(_p115(), _p117())
    second = bind_p115_replay_to_p117_retained_identity(_p115(), _p117())

    assert isinstance(first, RecoveryP115P117CompositionEvidence)
    assert first == second
    assert first.evidence_state == EVIDENCE_STATE
    assert first.automatic_control_allowed is False
    assert first.p115_contract_verified is True
    assert first.p117_contract_verified is True
    assert first.cross_evidence_identity_verified is True
    assert first.retained_p116_record_payload_sha256 == _sha("retained-p116-record")
    assert first.retained_p116_record_payload_size_bytes == 1217
    assert len(first.p115_p117_composition_binding_sha256) == 64


@pytest.mark.parametrize("field,kind", _FIELDS)
def test_p118_rejects_every_shared_identity_mismatch(field: str, kind: str) -> None:
    baseline = _p117()
    replacement = getattr(baseline, field) + 1 if kind == "int" else _sha(f"mismatch-{field}")
    with pytest.raises(ValueError, match="disagrees"):
        bind_p115_replay_to_p117_retained_identity(_p115(), replace(baseline, **{field: replacement}))


@pytest.mark.parametrize(
    "flag",
    [
        "expected_payload_identity_verified",
        "canonical_receipt_verified",
        "dependency_state_verified",
        "p110_p112_composition_binding_recomputed_verified",
    ],
)
def test_p118_rejects_weakened_p115_contract(flag: str) -> None:
    with pytest.raises(ValueError, match="P115 verification contract"):
        bind_p115_replay_to_p117_retained_identity(replace(_p115(), **{flag: False}), _p117())


@pytest.mark.parametrize(
    "flag",
    [
        "p116_evidence_state_verified",
        "p116_verification_flags_verified",
        "exact_payload_identity_verified",
        "canonical_record_verified",
        "semantic_agreement_verified",
    ],
)
def test_p118_rejects_weakened_p117_contract(flag: str) -> None:
    with pytest.raises(ValueError, match="P117 verification contract"):
        bind_p115_replay_to_p117_retained_identity(_p115(), replace(_p117(), **{flag: False}))


def test_p118_rejects_dependency_state_drift() -> None:
    with pytest.raises(ValueError, match="P115 evidence state"):
        bind_p115_replay_to_p117_retained_identity(replace(_p115(), evidence_state="drift"), _p117())
    with pytest.raises(ValueError, match="embedded P113"):
        bind_p115_replay_to_p117_retained_identity(replace(_p115(), p113_evidence_state="drift"), _p117())
    with pytest.raises(ValueError, match="P117 evidence state"):
        bind_p115_replay_to_p117_retained_identity(_p115(), replace(_p117(), evidence_state="drift"))


def test_p118_rejects_automatic_control_escalation() -> None:
    with pytest.raises(ValueError, match="P115 evidence must not grant"):
        bind_p115_replay_to_p117_retained_identity(replace(_p115(), automatic_control_allowed=True), _p117())
    with pytest.raises(ValueError, match="P117 evidence must not grant"):
        bind_p115_replay_to_p117_retained_identity(_p115(), replace(_p117(), automatic_control_allowed=True))


@pytest.mark.parametrize("field", [field for field, kind in _FIELDS if kind == "int"])
@pytest.mark.parametrize("bad", [True, 0, -1])
def test_p118_rejects_invalid_integer_identity_across_shared_fields(field: str, bad: object) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        bind_p115_replay_to_p117_retained_identity(replace(_p115(), **{field: bad}), _p117())


@pytest.mark.parametrize("field", [field for field, kind in _FIELDS if kind == "sha"])
@pytest.mark.parametrize("bad", ["A" * 64, "f" * 63, "g" * 64])
def test_p118_rejects_malformed_sha_identity_across_shared_fields(field: str, bad: object) -> None:
    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        bind_p115_replay_to_p117_retained_identity(replace(_p115(), **{field: bad}), _p117())


@pytest.mark.parametrize("bad", [True, 0, -9])
def test_p118_rejects_invalid_retained_record_size(bad: object) -> None:
    with pytest.raises(ValueError, match="retained P116 record size"):
        bind_p115_replay_to_p117_retained_identity(
            _p115(), replace(_p117(), stored_payload_size_bytes=bad)
        )


def test_p118_rejects_invalid_retained_record_sha() -> None:
    with pytest.raises(ValueError, match="retained P116 record SHA-256"):
        bind_p115_replay_to_p117_retained_identity(
            _p115(), replace(_p117(), stored_payload_sha256="bad")
        )


def test_p118_binding_commits_to_retained_record_identity() -> None:
    baseline = bind_p115_replay_to_p117_retained_identity(_p115(), _p117())
    changed_sha = bind_p115_replay_to_p117_retained_identity(
        _p115(), replace(_p117(), stored_payload_sha256=_sha("other-record"))
    )
    changed_size = bind_p115_replay_to_p117_retained_identity(
        _p115(), replace(_p117(), stored_payload_size_bytes=1218)
    )
    assert baseline.p115_p117_composition_binding_sha256 != changed_sha.p115_p117_composition_binding_sha256
    assert baseline.p115_p117_composition_binding_sha256 != changed_size.p115_p117_composition_binding_sha256


def test_p118_binding_commits_to_dependency_evidence_states(monkeypatch: pytest.MonkeyPatch) -> None:
    baseline = bind_p115_replay_to_p117_retained_identity(_p115(), _p117())
    monkeypatch.setattr("app.recovery_p118.P117_EVIDENCE_STATE", P117_EVIDENCE_STATE + "_ALT")
    altered_retained = replace(_p117(), evidence_state=P117_EVIDENCE_STATE + "_ALT")
    altered = bind_p115_replay_to_p117_retained_identity(_p115(), altered_retained)
    assert baseline.p115_p117_composition_binding_sha256 != altered.p115_p117_composition_binding_sha256


@pytest.mark.parametrize("left,right", [(object(), None), (None, object()), ("bad", "bad")])
def test_p118_rejects_incompatible_types(left: object, right: object) -> None:
    with pytest.raises(ValueError, match="incompatible type"):
        bind_p115_replay_to_p117_retained_identity(left, right)  # type: ignore[arg-type]


def test_p118_truth_boundary_is_explicit_and_non_scientific_overclaiming() -> None:
    evidence = bind_p115_replay_to_p117_retained_identity(_p115(), _p117())
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
