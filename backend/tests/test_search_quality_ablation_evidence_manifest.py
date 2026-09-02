from __future__ import annotations

from dataclasses import replace

import pytest

from app.search_quality_ablation_disclosure import AblationDisclosureReport
from app.search_quality_ablation_evidence_manifest import (
    EVIDENCE_STATE,
    build_ablation_research_evidence_manifest,
)
from app.search_quality_ablation_family import AblationFamilyMemberResult, SearchQualityAblationFamilyReport
from app.search_quality_ablation_preregistration import PredeclaredAblationFamilyReport
from app.search_quality_ablation_validity import AblationValidityThreatsReport


def _family() -> SearchQualityAblationFamilyReport:
    return SearchQualityAblationFamilyReport(
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
        members=(
            AblationFamilyMemberResult("without-calibration", 0.01, 0.03, True, True),
            AblationFamilyMemberResult("without-beam-search", 0.02, 0.04, True, True),
            AblationFamilyMemberResult("without-composition-score", 0.20, 0.20, True, False),
        ),
        all_effects_accepted=True,
        all_multiplicity_tests_accepted=False,
        acceptance_passed=False,
    )


def _preregistered() -> PredeclaredAblationFamilyReport:
    return PredeclaredAblationFamilyReport(
        plan_id="rq-search-ablation-plan-v1",
        plan_sha256="a" * 64,
        expected_family_size=3,
        observed_family_size=3,
        family_membership_exact=True,
        thresholds_bound=True,
        family_report=_family(),
        acceptance_passed=False,
    )


def _disclosure() -> AblationDisclosureReport:
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


def _validity() -> AblationValidityThreatsReport:
    return AblationValidityThreatsReport(
        plan_id="rq-search-ablation-plan-v1",
        plan_sha256="a" * 64,
        disclosure_sha256="b" * 64,
        family_size=3,
        threat_count=4,
        covered_categories=(
            "construct_validity",
            "external_validity",
            "internal_validity",
            "statistical_conclusion_validity",
        ),
        category_coverage_complete=True,
        threats_sha256="c" * 64,
        acceptance_passed=True,
    )


def test_manifest_binds_complete_evidence_chain_without_promoting_negative_results() -> None:
    report = build_ablation_research_evidence_manifest(_preregistered(), _disclosure(), _validity())
    assert report.plan_id == "rq-search-ablation-plan-v1"
    assert report.family_size == 3
    assert report.family_acceptance_passed is False
    assert report.disclosed_accepted_count == 2
    assert report.disclosed_not_accepted_count == 1
    assert report.integrity_passed is True
    assert report.evidence_state == EVIDENCE_STATE
    assert report.automatic_control_allowed is False
    payload = report.as_dict()
    assert len(payload["evidence_manifest_sha256"]) == 64
    assert "not an external timestamp" in payload["truth_boundary"]
    assert "benchmark or search superiority" in payload["truth_boundary"]


def test_manifest_is_deterministic_across_equivalent_member_order_and_label_case() -> None:
    first = build_ablation_research_evidence_manifest(_preregistered(), _disclosure(), _validity())
    family = _family()
    members = tuple(reversed(family.members))
    members = (replace(members[0], ablated_label=" WITHOUT-COMPOSITION-SCORE "),) + members[1:]
    second_prereg = replace(_preregistered(), family_report=replace(family, members=members))
    second = build_ablation_research_evidence_manifest(second_prereg, _disclosure(), _validity())
    assert first.evidence_manifest_sha256 == second.evidence_manifest_sha256


def test_manifest_hash_changes_when_bound_research_content_changes() -> None:
    first = build_ablation_research_evidence_manifest(_preregistered(), _disclosure(), _validity())
    changed_family = replace(_family(), protocol="rq-ablation-family-v3")
    changed = build_ablation_research_evidence_manifest(
        replace(_preregistered(), family_report=changed_family), _disclosure(), _validity()
    )
    assert first.evidence_manifest_sha256 != changed.evidence_manifest_sha256


def test_manifest_rejects_plan_and_disclosure_identity_drift() -> None:
    with pytest.raises(ValueError, match="plan_id mismatch"):
        build_ablation_research_evidence_manifest(
            _preregistered(), replace(_disclosure(), plan_id="other"), _validity()
        )
    with pytest.raises(ValueError, match="plan_sha256 mismatch"):
        build_ablation_research_evidence_manifest(
            _preregistered(), replace(_disclosure(), plan_sha256="d" * 64), _validity()
        )
    with pytest.raises(ValueError, match="disclosure_sha256 mismatch"):
        build_ablation_research_evidence_manifest(
            _preregistered(), _disclosure(), replace(_validity(), disclosure_sha256="d" * 64)
        )


def test_manifest_rejects_invalid_or_inconsistent_digests_and_family_sizes() -> None:
    with pytest.raises(ValueError, match="64-character hexadecimal"):
        build_ablation_research_evidence_manifest(
            replace(_preregistered(), plan_sha256="not-a-digest"), _disclosure(), _validity()
        )
    with pytest.raises(ValueError, match="multiplicity-aware family size"):
        build_ablation_research_evidence_manifest(
            replace(_preregistered(), family_report=replace(_family(), family_size=4)), _disclosure(), _validity()
        )
    with pytest.raises(ValueError, match="outcome counts"):
        build_ablation_research_evidence_manifest(
            _preregistered(), replace(_disclosure(), accepted_count=3), _validity()
        )


def test_manifest_rejects_incomplete_or_incompatible_evidence() -> None:
    with pytest.raises(ValueError, match="evidence_state"):
        build_ablation_research_evidence_manifest(
            replace(_preregistered(), evidence_state="OTHER"), _disclosure(), _validity()
        )
    with pytest.raises(ValueError, match="complete supplied-family disclosure"):
        build_ablation_research_evidence_manifest(
            _preregistered(), replace(_disclosure(), membership_complete=False), _validity()
        )
    with pytest.raises(ValueError, match="required-category coverage"):
        build_ablation_research_evidence_manifest(
            _preregistered(), _disclosure(), replace(_validity(), category_coverage_complete=False)
        )


def test_manifest_rejects_duplicate_normalized_family_members() -> None:
    family = _family()
    duplicate = replace(family.members[1], ablated_label=" WITHOUT-CALIBRATION ")
    with pytest.raises(ValueError, match="distinct normalized"):
        build_ablation_research_evidence_manifest(
            replace(_preregistered(), family_report=replace(family, members=(family.members[0], duplicate, family.members[2]))),
            _disclosure(),
            _validity(),
        )


def test_manifest_rejects_attempted_control_authority_at_every_bound_layer() -> None:
    with pytest.raises(ValueError, match="automatic control"):
        build_ablation_research_evidence_manifest(
            replace(_preregistered(), automatic_control_allowed=True), _disclosure(), _validity()
        )
    with pytest.raises(ValueError, match="automatic control"):
        build_ablation_research_evidence_manifest(
            _preregistered(), replace(_disclosure(), automatic_control_allowed=True), _validity()
        )
    with pytest.raises(ValueError, match="automatic control"):
        build_ablation_research_evidence_manifest(
            _preregistered(), _disclosure(), replace(_validity(), automatic_control_allowed=True)
        )
    family = replace(_family(), automatic_control_allowed=True)
    with pytest.raises(ValueError, match="automatic control"):
        build_ablation_research_evidence_manifest(
            replace(_preregistered(), family_report=family), _disclosure(), _validity()
        )
