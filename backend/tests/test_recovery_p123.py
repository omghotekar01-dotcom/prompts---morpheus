from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from app.recovery_p118 import EVIDENCE_STATE as P118_EVIDENCE_STATE
from app.recovery_p120 import RecoveryP119ReplayEvidence
from app.recovery_p122 import EVIDENCE_STATE as P122_EVIDENCE_STATE, RecoveryP121ReplayEvidence
from app.recovery_p123 import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    _FIELDS,
    RecoveryP120P122CompositionEvidence,
    bind_p120_replay_to_p122_retained_identity,
)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _shared() -> dict[str, object]:
    values: dict[str, object] = {}
    next_int = 37
    for field, kind in _FIELDS:
        if kind == "int":
            values[field] = next_int
            next_int += 31
        else:
            values[field] = _sha(field)
    return values


def _p120(**overrides: object) -> RecoveryP119ReplayEvidence:
    kwargs = {
        **_shared(),
        "expected_payload_identity_verified": True,
        "canonical_receipt_verified": True,
        "dependency_state_verified": True,
        "p115_p117_composition_binding_recomputed_verified": True,
        "p118_evidence_state": P118_EVIDENCE_STATE,
    }
    kwargs.update(overrides)
    return RecoveryP119ReplayEvidence(**kwargs)


def _p122(**overrides: object) -> RecoveryP121ReplayEvidence:
    kwargs = {
        **_shared(),
        "stored_payload_sha256": _sha("retained-p121-record"),
        "stored_payload_size_bytes": 1223,
        "source_path": "evidence/p121.json",
        "p121_evidence_state_verified": True,
        "p121_verification_flags_verified": True,
        "exact_payload_identity_verified": True,
        "canonical_record_verified": True,
        "semantic_agreement_verified": True,
    }
    kwargs.update(overrides)
    return RecoveryP121ReplayEvidence(**kwargs)


def test_p123_composes_deterministically_without_authority() -> None:
    first = bind_p120_replay_to_p122_retained_identity(_p120(), _p122())
    second = bind_p120_replay_to_p122_retained_identity(_p120(), _p122())
    assert isinstance(first, RecoveryP120P122CompositionEvidence)
    assert first == second
    assert first.evidence_state == EVIDENCE_STATE
    assert first.automatic_control_allowed is False
    assert first.p120_contract_verified is True
    assert first.p122_contract_verified is True
    assert first.cross_evidence_identity_verified is True
    assert first.retained_p121_record_payload_sha256 == _sha("retained-p121-record")
    assert first.retained_p121_record_payload_size_bytes == 1223
    assert len(first.p120_p122_composition_binding_sha256) == 64


@pytest.mark.parametrize("field,kind", _FIELDS)
def test_p123_rejects_every_shared_identity_mismatch(field: str, kind: str) -> None:
    baseline = _p122()
    replacement = getattr(baseline, field) + 1 if kind == "int" else _sha(f"mismatch-{field}")
    with pytest.raises(ValueError, match="disagrees"):
        bind_p120_replay_to_p122_retained_identity(_p120(), replace(baseline, **{field: replacement}))


@pytest.mark.parametrize("flag", ["expected_payload_identity_verified", "canonical_receipt_verified", "dependency_state_verified", "p115_p117_composition_binding_recomputed_verified"])
def test_p123_rejects_weakened_p120_contract(flag: str) -> None:
    with pytest.raises(ValueError, match="P120 verification contract"):
        bind_p120_replay_to_p122_retained_identity(replace(_p120(), **{flag: False}), _p122())


@pytest.mark.parametrize("flag", ["p121_evidence_state_verified", "p121_verification_flags_verified", "exact_payload_identity_verified", "canonical_record_verified", "semantic_agreement_verified"])
def test_p123_rejects_weakened_p122_contract(flag: str) -> None:
    with pytest.raises(ValueError, match="P122 verification contract"):
        bind_p120_replay_to_p122_retained_identity(_p120(), replace(_p122(), **{flag: False}))


def test_p123_rejects_dependency_state_drift() -> None:
    with pytest.raises(ValueError, match="P120 evidence state"):
        bind_p120_replay_to_p122_retained_identity(replace(_p120(), evidence_state="drift"), _p122())
    with pytest.raises(ValueError, match="embedded P118"):
        bind_p120_replay_to_p122_retained_identity(replace(_p120(), p118_evidence_state="drift"), _p122())
    with pytest.raises(ValueError, match="P122 evidence state"):
        bind_p120_replay_to_p122_retained_identity(_p120(), replace(_p122(), evidence_state="drift"))


def test_p123_rejects_automatic_control_escalation() -> None:
    with pytest.raises(ValueError, match="P120 evidence must not grant"):
        bind_p120_replay_to_p122_retained_identity(replace(_p120(), automatic_control_allowed=True), _p122())
    with pytest.raises(ValueError, match="P122 evidence must not grant"):
        bind_p120_replay_to_p122_retained_identity(_p120(), replace(_p122(), automatic_control_allowed=True))


@pytest.mark.parametrize("field", [field for field, kind in _FIELDS if kind == "int"])
@pytest.mark.parametrize("bad", [True, 0, -1])
def test_p123_rejects_invalid_integer_identity_across_shared_fields(field: str, bad: object) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        bind_p120_replay_to_p122_retained_identity(replace(_p120(), **{field: bad}), _p122())


@pytest.mark.parametrize("field", [field for field, kind in _FIELDS if kind == "sha"])
@pytest.mark.parametrize("bad", ["A" * 64, "f" * 63, "g" * 64])
def test_p123_rejects_malformed_sha_identity_across_shared_fields(field: str, bad: object) -> None:
    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        bind_p120_replay_to_p122_retained_identity(replace(_p120(), **{field: bad}), _p122())


@pytest.mark.parametrize("bad", [True, 0, -9])
def test_p123_rejects_invalid_retained_record_size(bad: object) -> None:
    with pytest.raises(ValueError, match="retained P121 record size"):
        bind_p120_replay_to_p122_retained_identity(_p120(), replace(_p122(), stored_payload_size_bytes=bad))


def test_p123_rejects_invalid_retained_record_sha() -> None:
    with pytest.raises(ValueError, match="retained P121 record SHA-256"):
        bind_p120_replay_to_p122_retained_identity(_p120(), replace(_p122(), stored_payload_sha256="bad"))


def test_p123_binding_commits_to_retained_record_identity() -> None:
    baseline = bind_p120_replay_to_p122_retained_identity(_p120(), _p122())
    changed_sha = bind_p120_replay_to_p122_retained_identity(_p120(), replace(_p122(), stored_payload_sha256=_sha("other-record")))
    changed_size = bind_p120_replay_to_p122_retained_identity(_p120(), replace(_p122(), stored_payload_size_bytes=1224))
    assert baseline.p120_p122_composition_binding_sha256 != changed_sha.p120_p122_composition_binding_sha256
    assert baseline.p120_p122_composition_binding_sha256 != changed_size.p120_p122_composition_binding_sha256


def test_p123_binding_commits_to_dependency_evidence_states(monkeypatch: pytest.MonkeyPatch) -> None:
    baseline = bind_p120_replay_to_p122_retained_identity(_p120(), _p122())
    monkeypatch.setattr("app.recovery_p123.P122_EVIDENCE_STATE", P122_EVIDENCE_STATE + "_ALT")
    altered = bind_p120_replay_to_p122_retained_identity(_p120(), replace(_p122(), evidence_state=P122_EVIDENCE_STATE + "_ALT"))
    assert baseline.p120_p122_composition_binding_sha256 != altered.p120_p122_composition_binding_sha256


@pytest.mark.parametrize("left,right", [(object(), None), (None, object()), ("bad", "bad")])
def test_p123_rejects_incompatible_types(left: object, right: object) -> None:
    with pytest.raises(ValueError, match="incompatible type"):
        bind_p120_replay_to_p122_retained_identity(left, right)  # type: ignore[arg-type]


def test_p123_truth_boundary_is_explicit_and_non_scientific_overclaiming() -> None:
    evidence = bind_p120_replay_to_p122_retained_identity(_p120(), _p122())
    assert evidence.as_dict()["truth_boundary"] == TRUTH_BOUNDARY
    for phrase in ("does not authenticate", "freshness/latest/global/monotonic", "coordinated rollback/replay", "authorize startup or mutation", "production readiness", "benchmark evidence", "novelty evidence", "automatic-control authority"):
        assert phrase in TRUTH_BOUNDARY
    assert evidence.automatic_control_allowed is False
