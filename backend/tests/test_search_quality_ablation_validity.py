from __future__ import annotations

from dataclasses import replace

import pytest

from app.search_quality_ablation_disclosure import AblationDisclosureReport
from app.search_quality_ablation_family import AblationFamilyMemberResult, SearchQualityAblationFamilyReport
from app.search_quality_ablation_preregistration import PredeclaredAblationFamilyReport
from app.search_quality_ablation_validity import (
    EVIDENCE_STATE,
    REQUIRED_CATEGORIES,
    ValidityThreatEntry,
    evaluate_ablation_validity_threats,
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


def _disclosure_report() -> AblationDisclosureReport:
    return AblationDisclosureReport(
        plan_id="rq-search-ablation-plan-v1",
        plan_sha256="a" * 64,
        family_size=3,
        disclosed_count=3,
        accepted_count=2,
        not_accepted_count=1,
        membership_complete=True,
        outcome_classification_exact=True,
        disclosure_sha256="b" * 64,
        acceptance_passed=True,
    )


def _threats() -> tuple[ValidityThreatEntry, ...]:
    return (
        ValidityThreatEntry(
            "construct validity",
            "Top-1 regret may not represent every deployment objective.",
            "Keep the declared metric definition fixed and report the limitation explicitly.",
            "medium",
        ),
        ValidityThreatEntry(
            "internal-validity",
            "Condition differences other than the intended ablation could bias the paired effect.",
            "Require identical measurement context, candidate universe, and measured costs before analysis.",
            "medium",
        ),
        ValidityThreatEntry(
            "external_validity",
            "The supplied workload sample may not represent other workloads or machines.",
            "Limit conclusions to the supplied sample and require separate replication for broader claims.",
            "high",
        ),
        ValidityThreatEntry(
            "statistical conclusion validity",
            "Small supplied workload families can yield unstable effect and p-value estimates.",
            "Report caller-declared thresholds and multiplicity-aware results without promoting them to universal claims.",
            "unknown",
        ),
    )


def test_validity_gate_binds_complete_four_category_register() -> None:
    report = evaluate_ablation_validity_threats(_preregistered_report(), _disclosure_report(), _threats())
    assert report.plan_id == "rq-search-ablation-plan-v1"
    assert report.plan_sha256 == "a" * 64
    assert report.disclosure_sha256 == "b" * 64
    assert report.family_size == 3
    assert report.threat_count == 4
    assert report.covered_categories == tuple(sorted(REQUIRED_CATEGORIES))
    assert report.category_coverage_complete is True
    assert report.acceptance_passed is True
    assert report.evidence_state == EVIDENCE_STATE
    assert report.automatic_control_allowed is False
    payload = report.as_dict()
    assert len(payload["threats_sha256"]) == 64
    assert "does not prove that the listed threats are exhaustive" in payload["truth_boundary"]
    assert "publication-grade evidence" in payload["truth_boundary"]


def test_validity_hash_is_deterministic_across_order_and_category_spelling() -> None:
    first = evaluate_ablation_validity_threats(_preregistered_report(), _disclosure_report(), _threats())
    entries = _threats()
    varied = (
        replace(entries[3], category=" STATISTICAL-CONCLUSION-VALIDITY "),
        entries[1],
        entries[0],
        entries[2],
    )
    second = evaluate_ablation_validity_threats(_preregistered_report(), _disclosure_report(), varied)
    assert first.threats_sha256 == second.threats_sha256


def test_validity_gate_rejects_missing_or_unknown_categories() -> None:
    with pytest.raises(ValueError, match="at least one entry"):
        evaluate_ablation_validity_threats(_preregistered_report(), _disclosure_report(), _threats()[:3])
    entries = list(_threats())
    entries[0] = replace(entries[0], category="operational_validity")
    with pytest.raises(ValueError, match="required validity categories"):
        evaluate_ablation_validity_threats(_preregistered_report(), _disclosure_report(), entries)


def test_validity_gate_rejects_duplicate_normalized_threats() -> None:
    entries = _threats() + (
        replace(_threats()[0], category="CONSTRUCT-VALIDITY", threat="  top-1 REGRET may not represent every deployment objective.  "),
    )
    with pytest.raises(ValueError, match="duplicate normalized threat"):
        evaluate_ablation_validity_threats(_preregistered_report(), _disclosure_report(), entries)


def test_validity_gate_rejects_empty_fields_and_invalid_residual_risk() -> None:
    entries = list(_threats())
    entries[0] = replace(entries[0], threat="   ")
    with pytest.raises(ValueError, match="threat cannot be empty"):
        evaluate_ablation_validity_threats(_preregistered_report(), _disclosure_report(), entries)
    entries = list(_threats())
    entries[0] = replace(entries[0], mitigation_or_control="   ")
    with pytest.raises(ValueError, match="mitigation_or_control"):
        evaluate_ablation_validity_threats(_preregistered_report(), _disclosure_report(), entries)
    entries = list(_threats())
    entries[0] = replace(entries[0], residual_risk="resolved")
    with pytest.raises(ValueError, match="residual_risk"):
        evaluate_ablation_validity_threats(_preregistered_report(), _disclosure_report(), entries)


def test_validity_gate_rejects_preregistration_disclosure_identity_drift() -> None:
    prereg = _preregistered_report()
    disclosure = _disclosure_report()
    with pytest.raises(ValueError, match="plan_id mismatch"):
        evaluate_ablation_validity_threats(prereg, replace(disclosure, plan_id="other"), _threats())
    with pytest.raises(ValueError, match="plan_sha256 mismatch"):
        evaluate_ablation_validity_threats(prereg, replace(disclosure, plan_sha256="c" * 64), _threats())
    with pytest.raises(ValueError, match="family_size mismatch"):
        evaluate_ablation_validity_threats(prereg, replace(disclosure, family_size=4), _threats())


def test_validity_gate_rejects_incomplete_or_incompatible_evidence() -> None:
    prereg = _preregistered_report()
    disclosure = _disclosure_report()
    with pytest.raises(ValueError, match="evidence_state"):
        evaluate_ablation_validity_threats(replace(prereg, evidence_state="OTHER"), disclosure, _threats())
    with pytest.raises(ValueError, match="evidence_state"):
        evaluate_ablation_validity_threats(prereg, replace(disclosure, evidence_state="OTHER"), _threats())
    with pytest.raises(ValueError, match="complete supplied-family disclosure"):
        evaluate_ablation_validity_threats(prereg, replace(disclosure, membership_complete=False), _threats())
    with pytest.raises(ValueError, match="exact outcome classification"):
        evaluate_ablation_validity_threats(prereg, replace(disclosure, outcome_classification_exact=False), _threats())


def test_validity_gate_rejects_attempted_control_authority() -> None:
    with pytest.raises(ValueError, match="automatic control"):
        evaluate_ablation_validity_threats(
            replace(_preregistered_report(), automatic_control_allowed=True), _disclosure_report(), _threats()
        )
    with pytest.raises(ValueError, match="automatic control"):
        evaluate_ablation_validity_threats(
            _preregistered_report(), replace(_disclosure_report(), automatic_control_allowed=True), _threats()
        )
