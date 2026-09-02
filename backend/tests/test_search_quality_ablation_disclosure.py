from __future__ import annotations

from dataclasses import replace

import pytest

from app.search_quality_ablation_family import AblationFamilyMemberResult, SearchQualityAblationFamilyReport
from app.search_quality_ablation_preregistration import PredeclaredAblationFamilyReport
from app.search_quality_ablation_disclosure import (
    EVIDENCE_STATE,
    AblationOutcomeDisclosure,
    evaluate_ablation_outcome_disclosure,
)


def _preregistered_report() -> PredeclaredAblationFamilyReport:
    members = (
        AblationFamilyMemberResult("without-calibration", 0.01, 0.03, True, True),
        AblationFamilyMemberResult("without-beam-search", 0.02, 0.04, True, True),
        AblationFamilyMemberResult("without-composition-score", 0.20, 0.20, True, False),
    )
    family = SearchQualityAblationFamilyReport(
        measurement_source_id="heldout-family-a",
        protocol="rq-ablation-family-v2",
        machine_fingerprint="machine-a",
        reference_label="full-model",
        workload_count=8,
        candidate_count=24,
        top_k=3,
        family_size=3,
        family_wise_alpha=0.05,
        correction_method="holm_step_down_family_wise_error_control",
        members=members,
        all_effects_accepted=True,
        all_multiplicity_tests_accepted=False,
        acceptance_passed=False,
    )
    return PredeclaredAblationFamilyReport(
        plan_id="rq-search-ablation-plan-v1",
        plan_sha256="a" * 64,
        expected_family_size=3,
        observed_family_size=3,
        family_membership_exact=True,
        thresholds_bound=True,
        family_report=family,
        acceptance_passed=False,
    )


def _disclosures() -> tuple[AblationOutcomeDisclosure, ...]:
    return (
        AblationOutcomeDisclosure("without-calibration", "accepted", "Effect and Holm-adjusted test both met the declared limits."),
        AblationOutcomeDisclosure("without-beam-search", "accepted", "Effect and Holm-adjusted test both met the declared limits."),
        AblationOutcomeDisclosure("without-composition-score", "not_accepted", "Multiplicity-aware statistical acceptance was not met."),
    )


def test_disclosure_gate_requires_and_records_negative_result() -> None:
    report = evaluate_ablation_outcome_disclosure(_preregistered_report(), _disclosures())
    assert report.family_size == 3
    assert report.disclosed_count == 3
    assert report.accepted_count == 2
    assert report.not_accepted_count == 1
    assert report.membership_complete is True
    assert report.outcome_classification_exact is True
    assert report.acceptance_passed is True
    assert report.evidence_state == EVIDENCE_STATE
    assert report.automatic_control_allowed is False
    payload = report.as_dict()
    assert len(payload["disclosure_sha256"]) == 64
    assert "not proof that the family itself was externally preregistered" in payload["truth_boundary"]
    assert "selective reporting" in payload["truth_boundary"]


def test_disclosure_hash_is_deterministic_across_order_and_label_case() -> None:
    first = evaluate_ablation_outcome_disclosure(_preregistered_report(), _disclosures())
    entries = _disclosures()
    varied = (
        replace(entries[2], ablated_label=" WITHOUT-COMPOSITION-SCORE "),
        entries[0],
        entries[1],
    )
    second = evaluate_ablation_outcome_disclosure(_preregistered_report(), varied)
    assert first.disclosure_sha256 == second.disclosure_sha256


def test_disclosure_gate_rejects_omitted_extra_or_substituted_members() -> None:
    entries = _disclosures()
    with pytest.raises(ValueError, match="count"):
        evaluate_ablation_outcome_disclosure(_preregistered_report(), entries[:2])
    with pytest.raises(ValueError, match="count"):
        evaluate_ablation_outcome_disclosure(
            _preregistered_report(), entries + (AblationOutcomeDisclosure("extra", "accepted", "extra"),)
        )
    with pytest.raises(ValueError, match="membership"):
        evaluate_ablation_outcome_disclosure(
            _preregistered_report(), (entries[0], entries[1], AblationOutcomeDisclosure("different", "not_accepted", "different"))
        )


def test_disclosure_gate_rejects_duplicate_normalized_labels() -> None:
    entries = _disclosures()
    duplicated = (entries[0], replace(entries[1], ablated_label=" WITHOUT-CALIBRATION "), entries[2])
    with pytest.raises(ValueError, match="distinct normalized"):
        evaluate_ablation_outcome_disclosure(_preregistered_report(), duplicated)


def test_disclosure_gate_rejects_outcome_misclassification() -> None:
    entries = _disclosures()
    with pytest.raises(ValueError, match="outcome does not match"):
        evaluate_ablation_outcome_disclosure(
            _preregistered_report(), (entries[0], entries[1], replace(entries[2], outcome="accepted"))
        )


def test_disclosure_gate_rejects_empty_note_and_invalid_outcome() -> None:
    entries = _disclosures()
    with pytest.raises(ValueError, match="interpretation_note"):
        evaluate_ablation_outcome_disclosure(
            _preregistered_report(), (replace(entries[0], interpretation_note="   "), entries[1], entries[2])
        )
    with pytest.raises(ValueError, match="outcome must"):
        evaluate_ablation_outcome_disclosure(
            _preregistered_report(), (replace(entries[0], outcome="significant"), entries[1], entries[2])
        )


def test_disclosure_gate_rejects_incompatible_or_control_authorizing_evidence() -> None:
    base = _preregistered_report()
    with pytest.raises(ValueError, match="evidence_state"):
        evaluate_ablation_outcome_disclosure(replace(base, evidence_state="OTHER"), _disclosures())
    with pytest.raises(ValueError, match="automatic control"):
        evaluate_ablation_outcome_disclosure(replace(base, automatic_control_allowed=True), _disclosures())
    with pytest.raises(ValueError, match="family evidence"):
        evaluate_ablation_outcome_disclosure(
            replace(base, family_report=replace(base.family_report, automatic_control_allowed=True)), _disclosures()
        )


def test_disclosure_gate_rejects_unbound_or_inconsistent_preregistration() -> None:
    base = _preregistered_report()
    with pytest.raises(ValueError, match="exact family"):
        evaluate_ablation_outcome_disclosure(replace(base, family_membership_exact=False), _disclosures())
    with pytest.raises(ValueError, match="threshold binding"):
        evaluate_ablation_outcome_disclosure(replace(base, thresholds_bound=False), _disclosures())
    with pytest.raises(ValueError, match="family size"):
        evaluate_ablation_outcome_disclosure(replace(base, expected_family_size=4), _disclosures())
