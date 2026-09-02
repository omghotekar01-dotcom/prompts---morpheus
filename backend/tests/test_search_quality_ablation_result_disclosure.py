from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.search_quality_ablation_disclosure import AblationDisclosureReport
from app.search_quality_ablation_result_disclosure import (
    EVIDENCE_STATE,
    verify_ablation_result_disclosure_consistency,
)
from app.search_quality_ablation_result_outcome import AblationResultOutcomeVerification

PLAN_SHA = "aa" * 32
DISCLOSURE_SHA = "bb" * 32
OUTCOME_SHA = "cc" * 32


def _disclosure() -> AblationDisclosureReport:
    return AblationDisclosureReport(
        plan_id="rq-search-ablation-plan-v1",
        plan_sha256=PLAN_SHA,
        family_size=3,
        disclosed_count=3,
        accepted_count=2,
        not_accepted_count=1,
        membership_complete=True,
        outcome_classification_exact=True,
        disclosure_sha256=DISCLOSURE_SHA,
        acceptance_passed=True,
    )


def _document(disclosure: AblationDisclosureReport | None = None, **overrides: object) -> bytes:
    report = disclosure or _disclosure()
    value: dict[str, object] = {
        "schema": "morpheus.ablation-result/v1",
        "accepted": False,
        "family": {"family_size": report.family_size},
        "disclosure": {
            "plan_id": report.plan_id,
            "plan_sha256": report.plan_sha256,
            "disclosure_sha256": report.disclosure_sha256,
            "family_size": report.family_size,
            "disclosed_count": report.disclosed_count,
            "accepted_count": report.accepted_count,
            "not_accepted_count": report.not_accepted_count,
            "membership_complete": report.membership_complete,
            "outcome_classification_exact": report.outcome_classification_exact,
        },
        "automatic_control_allowed": False,
    }
    value.update(overrides)
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _outcome(raw: bytes) -> AblationResultOutcomeVerification:
    return AblationResultOutcomeVerification(
        semantic_verification_sha256="dd" * 32,
        result_artifact_sha256=hashlib.sha256(raw).hexdigest(),
        measurement_source_id="heldout-family-a",
        protocol="rq-ablation-family-v2",
        machine_fingerprint="machine-a",
        reference_label="full-model",
        family_size=3,
        family_wise_alpha=0.05,
        correction_method="holm_step_down_family_wise_error_control",
        acceptance_passed=False,
        member_count=3,
        outcome_verification_sha256=OUTCOME_SHA,
        outcome_consistency_verified=True,
    )


def test_result_disclosure_consistency_binds_complete_negative_result_reporting() -> None:
    disclosure = _disclosure()
    raw = _document(disclosure)
    report = verify_ablation_result_disclosure_consistency(_outcome(raw), disclosure, result_artifact=raw)
    assert report.disclosure_consistency_verified is True
    assert report.family_size == 3
    assert report.disclosed_count == 3
    assert report.accepted_count == 2
    assert report.not_accepted_count == 1
    assert report.evidence_state == EVIDENCE_STATE
    assert report.automatic_control_allowed is False
    truth = report.as_dict()["truth_boundary"]
    assert "completeness beyond the supplied predeclared family" in truth
    assert "no benchmark/search superiority" in truth


def test_result_disclosure_identity_is_deterministic_for_identical_bound_evidence() -> None:
    disclosure = _disclosure()
    raw = _document(disclosure)
    first = verify_ablation_result_disclosure_consistency(_outcome(raw), disclosure, result_artifact=raw)
    second = verify_ablation_result_disclosure_consistency(_outcome(raw), disclosure, result_artifact=raw)
    assert first.disclosure_verification_sha256 == second.disclosure_verification_sha256


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("plan_id", "other-plan"),
        ("plan_sha256", "11" * 32),
        ("disclosure_sha256", "22" * 32),
        ("family_size", 4),
        ("disclosed_count", 2),
        ("accepted_count", 1),
        ("not_accepted_count", 2),
    ],
)
def test_result_disclosure_consistency_rejects_declared_identity_or_count_drift(field: str, value: object) -> None:
    disclosure = _disclosure()
    document = json.loads(_document(disclosure))
    document["disclosure"][field] = value
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match=f"disclosure.{field}"):
        verify_ablation_result_disclosure_consistency(_outcome(raw), disclosure, result_artifact=raw)


def test_result_disclosure_consistency_rejects_missing_or_false_completeness_claims() -> None:
    disclosure = _disclosure()
    document = json.loads(_document(disclosure))
    document.pop("disclosure")
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="disclosure must be an object"):
        verify_ablation_result_disclosure_consistency(_outcome(raw), disclosure, result_artifact=raw)

    for field in ("membership_complete", "outcome_classification_exact"):
        document = json.loads(_document(disclosure))
        document["disclosure"][field] = False
        raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        with pytest.raises(ValueError, match=field):
            verify_ablation_result_disclosure_consistency(_outcome(raw), disclosure, result_artifact=raw)


def test_result_disclosure_consistency_rejects_invalid_declared_types() -> None:
    disclosure = _disclosure()
    document = json.loads(_document(disclosure))
    document["disclosure"]["family_size"] = True
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="non-negative integer"):
        verify_ablation_result_disclosure_consistency(_outcome(raw), disclosure, result_artifact=raw)

    document = json.loads(_document(disclosure))
    document["disclosure"]["membership_complete"] = 1
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="boolean"):
        verify_ablation_result_disclosure_consistency(_outcome(raw), disclosure, result_artifact=raw)


def test_result_disclosure_consistency_rejects_inconsistent_p33_counts_or_family_size() -> None:
    raw = _document()
    outcome = _outcome(raw)
    disclosure = _disclosure()
    with pytest.raises(ValueError, match="disclosed count"):
        verify_ablation_result_disclosure_consistency(
            outcome, replace(disclosure, disclosed_count=2), result_artifact=raw
        )
    with pytest.raises(ValueError, match="sum to family size"):
        verify_ablation_result_disclosure_consistency(
            outcome, replace(disclosure, accepted_count=3), result_artifact=raw
        )
    with pytest.raises(ValueError, match="must match the P40"):
        verify_ablation_result_disclosure_consistency(
            outcome, replace(disclosure, family_size=4, disclosed_count=4, not_accepted_count=2), result_artifact=raw
        )


def test_result_disclosure_consistency_rejects_unverified_or_control_authorizing_inputs() -> None:
    disclosure = _disclosure()
    raw = _document(disclosure)
    outcome = _outcome(raw)
    with pytest.raises(ValueError, match="evidence_state"):
        verify_ablation_result_disclosure_consistency(
            replace(outcome, evidence_state="OTHER"), disclosure, result_artifact=raw
        )
    with pytest.raises(ValueError, match="must be verified"):
        verify_ablation_result_disclosure_consistency(
            replace(outcome, outcome_consistency_verified=False), disclosure, result_artifact=raw
        )
    with pytest.raises(ValueError, match="automatic control"):
        verify_ablation_result_disclosure_consistency(
            replace(outcome, automatic_control_allowed=True), disclosure, result_artifact=raw
        )
    with pytest.raises(ValueError, match="evidence_state"):
        verify_ablation_result_disclosure_consistency(
            outcome, replace(disclosure, evidence_state="OTHER"), result_artifact=raw
        )
    with pytest.raises(ValueError, match="automatic control"):
        verify_ablation_result_disclosure_consistency(
            outcome, replace(disclosure, automatic_control_allowed=True), result_artifact=raw
        )


def test_result_disclosure_consistency_rejects_byte_drift_and_control_promotion() -> None:
    disclosure = _disclosure()
    bound = _document(disclosure)
    changed = _document(disclosure, note="changed")
    with pytest.raises(ValueError, match="bytes do not match"):
        verify_ablation_result_disclosure_consistency(_outcome(bound), disclosure, result_artifact=changed)

    document = json.loads(bound)
    document["automatic_control_allowed"] = True
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="explicitly set automatic_control_allowed to false"):
        verify_ablation_result_disclosure_consistency(_outcome(raw), disclosure, result_artifact=raw)
