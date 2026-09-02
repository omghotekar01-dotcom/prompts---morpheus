from __future__ import annotations

from dataclasses import replace

import pytest

from app.search_quality_ablation import SearchQualityAblationReport
from app.search_quality_ablation_preregistration import (
    EVIDENCE_STATE,
    AblationAnalysisPlan,
    evaluate_predeclared_ablation_family,
)


def _report(label: str, *, p_value: float = 0.01) -> SearchQualityAblationReport:
    return SearchQualityAblationReport(
        measurement_source_id="heldout-family-a",
        protocol="rq-ablation-family-v2",
        machine_fingerprint="machine-a",
        reference_label="full-model",
        ablated_label=label,
        workload_count=8,
        candidate_count=24,
        top_k=3,
        reference_mean_top1_regret_ratio=0.05,
        ablated_mean_top1_regret_ratio=0.25,
        mean_regret_ratio_improvement=0.20,
        median_regret_ratio_improvement=0.20,
        improved_workload_count=8,
        tied_workload_count=0,
        worsened_workload_count=0,
        randomization_method="exact_sign_flip",
        randomization_rounds=256,
        randomization_seed=17,
        one_sided_p_value=p_value,
        minimum_required_mean_regret_ratio_improvement=0.10,
        maximum_allowed_one_sided_p_value=0.05,
        effect_acceptance_passed=True,
        statistical_acceptance_passed=p_value <= 0.05,
        acceptance_passed=p_value <= 0.05,
    )


def _plan(**overrides) -> AblationAnalysisPlan:
    values = {
        "plan_id": "rq-search-ablation-plan-v1",
        "measurement_source_id": "heldout-family-a",
        "protocol": "rq-ablation-family-v2",
        "machine_fingerprint": "machine-a",
        "reference_label": "full-model",
        "workload_count": 8,
        "candidate_count": 24,
        "top_k": 3,
        "expected_ablated_labels": ("without-calibration", "without-beam-search", "without-composition-score"),
        "minimum_required_mean_regret_ratio_improvement": 0.10,
        "maximum_allowed_one_sided_p_value": 0.05,
        "family_wise_alpha": 0.05,
    }
    values.update(overrides)
    return AblationAnalysisPlan(**values)


def _reports() -> tuple[SearchQualityAblationReport, ...]:
    return (
        _report("without-calibration", p_value=0.01),
        _report("without-beam-search", p_value=0.02),
        _report("without-composition-score", p_value=0.03),
    )


def test_predeclared_gate_binds_exact_family_and_thresholds() -> None:
    report = evaluate_predeclared_ablation_family(_plan(), _reports())
    assert report.expected_family_size == 3
    assert report.observed_family_size == 3
    assert report.family_membership_exact is True
    assert report.thresholds_bound is True
    assert report.family_report.acceptance_passed is True
    assert report.acceptance_passed is True
    assert report.evidence_state == EVIDENCE_STATE
    assert report.automatic_control_allowed is False
    payload = report.as_dict()
    assert len(payload["plan_sha256"]) == 64
    assert "does not prove when the plan was authored" in payload["truth_boundary"]
    assert "selective reporting" in payload["truth_boundary"]
    assert "production-control" in payload["truth_boundary"]


def test_plan_hash_is_canonical_across_label_order_and_outer_whitespace() -> None:
    first = _plan()
    second = _plan(
        plan_id=" rq-search-ablation-plan-v1 ",
        expected_ablated_labels=(" without-composition-score ", "without-calibration", "without-beam-search"),
    )
    assert first.sha256() == second.sha256()


def test_gate_rejects_missing_extra_or_substituted_family_members() -> None:
    reports = _reports()
    with pytest.raises(ValueError, match="family size"):
        evaluate_predeclared_ablation_family(_plan(), reports[:2])
    with pytest.raises(ValueError, match="family size"):
        evaluate_predeclared_ablation_family(_plan(), reports + (_report("extra"),))
    with pytest.raises(ValueError, match="membership"):
        evaluate_predeclared_ablation_family(_plan(), (reports[0], reports[1], _report("different")))


def test_gate_matches_family_membership_after_normalization() -> None:
    reports = _reports()
    varied = (
        replace(reports[0], ablated_label=" WITHOUT-CALIBRATION "),
        reports[1],
        reports[2],
    )
    result = evaluate_predeclared_ablation_family(_plan(), varied)
    assert result.family_membership_exact is True


def test_gate_rejects_threshold_drift() -> None:
    reports = _reports()
    with pytest.raises(ValueError, match="effect-size threshold"):
        evaluate_predeclared_ablation_family(
            _plan(), (replace(reports[0], minimum_required_mean_regret_ratio_improvement=0.05), reports[1], reports[2])
        )
    with pytest.raises(ValueError, match="statistical threshold"):
        evaluate_predeclared_ablation_family(
            _plan(), (replace(reports[0], maximum_allowed_one_sided_p_value=0.10), reports[1], reports[2])
        )


def test_gate_rejects_context_drift() -> None:
    reports = _reports()
    with pytest.raises(ValueError, match="measurement_source_id"):
        evaluate_predeclared_ablation_family(_plan(), (replace(reports[0], measurement_source_id="other"), *reports[1:]))
    with pytest.raises(ValueError, match="protocol"):
        evaluate_predeclared_ablation_family(_plan(), (replace(reports[0], protocol="other"), *reports[1:]))
    with pytest.raises(ValueError, match="machine_fingerprint"):
        evaluate_predeclared_ablation_family(_plan(), (replace(reports[0], machine_fingerprint="other"), *reports[1:]))
    with pytest.raises(ValueError, match="top_k"):
        evaluate_predeclared_ablation_family(_plan(), (replace(reports[0], top_k=1), *reports[1:]))


def test_gate_rejects_duplicate_plan_or_observed_labels_and_invalid_limits() -> None:
    with pytest.raises(ValueError, match="distinct after normalization"):
        evaluate_predeclared_ablation_family(
            _plan(expected_ablated_labels=("a", " A ")), (_report("a"), _report("b"))
        )
    reports = _reports()
    with pytest.raises(ValueError, match="distinct after normalization"):
        evaluate_predeclared_ablation_family(_plan(), (reports[0], replace(reports[1], ablated_label=reports[0].ablated_label), reports[2]))
    with pytest.raises(ValueError, match="non-negative"):
        evaluate_predeclared_ablation_family(_plan(minimum_required_mean_regret_ratio_improvement=-0.1), reports)
    with pytest.raises(ValueError, match="family_wise_alpha"):
        evaluate_predeclared_ablation_family(_plan(family_wise_alpha=0.0), reports)


def test_gate_rejects_control_authority_and_incompatible_evidence_state() -> None:
    reports = _reports()
    with pytest.raises(ValueError, match="automatic control"):
        evaluate_predeclared_ablation_family(_plan(), (replace(reports[0], automatic_control_allowed=True), *reports[1:]))
    with pytest.raises(ValueError, match="evidence_state"):
        evaluate_predeclared_ablation_family(_plan(), (replace(reports[0], evidence_state="OTHER"), *reports[1:]))


def test_predeclared_report_is_deterministic() -> None:
    first = evaluate_predeclared_ablation_family(_plan(), _reports())
    second = evaluate_predeclared_ablation_family(_plan(), _reports())
    assert first == second
    assert first.as_dict() == second.as_dict()
