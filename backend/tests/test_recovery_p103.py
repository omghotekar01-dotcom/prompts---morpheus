from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding import (
    EVIDENCE_STATE as P98_EVIDENCE_STATE,
)
from app.recovery_p100 import (
    RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingReceiptReplayEvidence,
)
from app.recovery_p102 import EVIDENCE_STATE as P102_EVIDENCE_STATE, RecoveryP101ReplayEvidence
from app.recovery_p103 import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    _FIELDS,
    RecoveryP100P102CompositionEvidence,
    bind_p100_replay_to_p102_retained_identity,
)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _shared() -> dict[str, object]:
    values: dict[str, object] = {}
    next_int = 7
    for field, kind in _FIELDS:
        if kind == "int":
            values[field] = next_int
            next_int += 11
        else:
            values[field] = _sha(field)
    return values


def _p100(**overrides: object) -> RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingReceiptReplayEvidence:
    kwargs = {
        **_shared(),
        "expected_payload_identity_verified": True,
        "canonical_receipt_verified": True,
        "dependency_state_verified": True,
        "replayed_receipt_retained_identity_binding_recomputed_verified": True,
        "p98_evidence_state": P98_EVIDENCE_STATE,
    }
    kwargs.update(overrides)
    return RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingReceiptReplayEvidence(**kwargs)


def _p102(**overrides: object) -> RecoveryP101ReplayEvidence:
    kwargs = {
        **_shared(),
        "stored_payload_sha256": _sha("retained-p101-record"),
        "stored_payload_size_bytes": 409,
        "source_path": "evidence/p101.json",
        "p101_evidence_state_verified": True,
        "p101_verification_flags_verified": True,
        "exact_payload_identity_verified": True,
        "canonical_record_verified": True,
        "semantic_agreement_verified": True,
    }
    kwargs.update(overrides)
    return RecoveryP101ReplayEvidence(**kwargs)


def test_p103_composes_deterministically_without_authority() -> None:
    first = bind_p100_replay_to_p102_retained_identity(_p100(), _p102())
    second = bind_p100_replay_to_p102_retained_identity(_p100(), _p102())

    assert isinstance(first, RecoveryP100P102CompositionEvidence)
    assert first == second
    assert first.evidence_state == EVIDENCE_STATE
    assert first.automatic_control_allowed is False
    assert first.p100_contract_verified is True
    assert first.p102_contract_verified is True
    assert first.cross_evidence_identity_verified is True
    assert first.retained_p101_record_payload_sha256 == _sha("retained-p101-record")
    assert first.retained_p101_record_payload_size_bytes == 409
    assert len(first.p100_p102_composition_binding_sha256) == 64


@pytest.mark.parametrize("field,kind", _FIELDS)
def test_p103_rejects_every_shared_identity_mismatch(field: str, kind: str) -> None:
    baseline = _p102()
    replacement = getattr(baseline, field) + 1 if kind == "int" else _sha(f"mismatch-{field}")
    with pytest.raises(ValueError, match="disagrees"):
        bind_p100_replay_to_p102_retained_identity(_p100(), replace(baseline, **{field: replacement}))


@pytest.mark.parametrize(
    "flag",
    [
        "expected_payload_identity_verified",
        "canonical_receipt_verified",
        "dependency_state_verified",
        "replayed_receipt_retained_identity_binding_recomputed_verified",
    ],
)
def test_p103_rejects_weakened_p100_contract(flag: str) -> None:
    with pytest.raises(ValueError, match="P100 verification contract"):
        bind_p100_replay_to_p102_retained_identity(replace(_p100(), **{flag: False}), _p102())


@pytest.mark.parametrize(
    "flag",
    [
        "p101_evidence_state_verified",
        "p101_verification_flags_verified",
        "exact_payload_identity_verified",
        "canonical_record_verified",
        "semantic_agreement_verified",
    ],
)
def test_p103_rejects_weakened_p102_contract(flag: str) -> None:
    with pytest.raises(ValueError, match="P102 verification contract"):
        bind_p100_replay_to_p102_retained_identity(_p100(), replace(_p102(), **{flag: False}))


def test_p103_rejects_dependency_state_drift() -> None:
    with pytest.raises(ValueError, match="P100 evidence state"):
        bind_p100_replay_to_p102_retained_identity(replace(_p100(), evidence_state="drift"), _p102())
    with pytest.raises(ValueError, match="embedded P98"):
        bind_p100_replay_to_p102_retained_identity(replace(_p100(), p98_evidence_state="drift"), _p102())
    with pytest.raises(ValueError, match="P102 evidence state"):
        bind_p100_replay_to_p102_retained_identity(_p100(), replace(_p102(), evidence_state="drift"))


def test_p103_rejects_automatic_control_escalation() -> None:
    with pytest.raises(ValueError, match="P100 evidence must not grant"):
        bind_p100_replay_to_p102_retained_identity(replace(_p100(), automatic_control_allowed=True), _p102())
    with pytest.raises(ValueError, match="P102 evidence must not grant"):
        bind_p100_replay_to_p102_retained_identity(_p100(), replace(_p102(), automatic_control_allowed=True))


@pytest.mark.parametrize("bad", [True, 0, -1])
def test_p103_rejects_invalid_positive_integer_identity(bad: object) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        bind_p100_replay_to_p102_retained_identity(replace(_p100(), sequence=bad), _p102())


@pytest.mark.parametrize("bad", ["A" * 64, "f" * 63, "g" * 64, 123])
def test_p103_rejects_malformed_sha_identity(bad: object) -> None:
    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        bind_p100_replay_to_p102_retained_identity(replace(_p100(), lineage_sha256=bad), _p102())


@pytest.mark.parametrize("bad", [True, 0, -9])
def test_p103_rejects_invalid_retained_record_size(bad: object) -> None:
    with pytest.raises(ValueError, match="retained P101 record size"):
        bind_p100_replay_to_p102_retained_identity(_p100(), replace(_p102(), stored_payload_size_bytes=bad))


def test_p103_rejects_invalid_retained_record_sha() -> None:
    with pytest.raises(ValueError, match="retained P101 record SHA-256"):
        bind_p100_replay_to_p102_retained_identity(_p100(), replace(_p102(), stored_payload_sha256="bad"))


def test_p103_binding_commits_to_retained_record_identity() -> None:
    baseline = bind_p100_replay_to_p102_retained_identity(_p100(), _p102())
    changed_sha = bind_p100_replay_to_p102_retained_identity(
        _p100(), replace(_p102(), stored_payload_sha256=_sha("other-record"))
    )
    changed_size = bind_p100_replay_to_p102_retained_identity(
        _p100(), replace(_p102(), stored_payload_size_bytes=410)
    )
    assert baseline.p100_p102_composition_binding_sha256 != changed_sha.p100_p102_composition_binding_sha256
    assert baseline.p100_p102_composition_binding_sha256 != changed_size.p100_p102_composition_binding_sha256


def test_p103_binding_commits_to_dependency_evidence_states(monkeypatch: pytest.MonkeyPatch) -> None:
    baseline = bind_p100_replay_to_p102_retained_identity(_p100(), _p102())
    monkeypatch.setattr("app.recovery_p103.P102_EVIDENCE_STATE", P102_EVIDENCE_STATE + "_ALT")
    altered_retained = replace(_p102(), evidence_state=P102_EVIDENCE_STATE + "_ALT")
    altered = bind_p100_replay_to_p102_retained_identity(_p100(), altered_retained)
    assert baseline.p100_p102_composition_binding_sha256 != altered.p100_p102_composition_binding_sha256


@pytest.mark.parametrize("left,right", [(object(), None), (None, object()), ("bad", "bad")])
def test_p103_rejects_incompatible_types(left: object, right: object) -> None:
    with pytest.raises(ValueError, match="incompatible type"):
        bind_p100_replay_to_p102_retained_identity(left, right)  # type: ignore[arg-type]


def test_p103_truth_boundary_is_explicit_and_non_scientific_overclaiming() -> None:
    evidence = bind_p100_replay_to_p102_retained_identity(_p100(), _p102())
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
