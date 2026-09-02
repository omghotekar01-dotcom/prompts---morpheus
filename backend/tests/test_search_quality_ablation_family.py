from __future__ import annotations

from dataclasses import replace

import pytest

from app.search_quality_ablation import EVIDENCE_STATE as ABLATION_EVIDENCE_STATE
from app.search_quality_ablation import SearchQualityAblationReport
from app.search_quality_ablation_family import EVIDENCE_STATE, evaluate_search_quality_ablation_family


def _report(label: str, *, p_value: float, effect_passed: bool = True) -> SearchQualityAblationReport:
    return SearchQualityAblationReport(
        measurement_source_id="heldout-family-a",
        protocol="rq-ablation-family-v1",
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
        effect_acceptance_passed=effect_passed,
        statistical_acceptance_passed=p_value <= 0.05,
        acceptance_passed=effect_passed and p_value <= 0.05,
    )


def _family(*reports: SearchQualityAblationReport, **overrides):
    if not reports:
        reports = (
            _report("without-calibration", p_value=0.01),
            _report("without-beam-search", p_value=0.02),
            _report("without-composition-score", p_value=0.03),
        )
    kwargs = {"family_wise_alpha": 0.05, "minimum_required_ablations": 2}
    kwargs.update(overrides)
    return evaluate_search_quality_ablation_family(reports, **kwargs)


def test_holm_family_gate_accepts_only_when_all_adjusted_tests_and_effects_pass() -> None:
    report = _family()
    assert report.family_size == 3
    assert report.correction_method == "holm_step_down_family_wise_error_control"
    assert [member.holm_adjusted_p_value for member in report.members] == pytest.approx([0.03, 0.04, 0.04])
    assert report.all_effects_accepted is True
    assert report.all_multiplicity_tests_accepted is True
    assert report.acceptance_passed is True
    assert report.evidence_state == EVIDENCE_STATE
    assert report.automatic_control_allowed is False
    payload = report.as_dict()
    assert "predeclared inclusion" in payload["truth_boundary"]
    assert "selective reporting" in payload["truth_boundary"]
    assert "production-control" in payload["truth_boundary"]


def test_raw_significance_can_fail_after_family_wise_correction() -> None:
    report = _family(
        _report("a", p_value=0.02),
        _report("b", p_value=0.03),
        _report("c", p_value=0.04),
    )
    assert all(member.raw_one_sided_p_value <= 0.05 for member in report.members)
    assert report.members[0].holm_adjusted_p_value == pytest.approx(0.06)
    assert report.all_multiplicity_tests_accepted is False
    assert report.acceptance_passed is False


def test_family_requires_constituent_effect_acceptance_independently_of_p_value() -> None:
    report = _family(
        _report("a", p_value=0.005),
        _report("b", p_value=0.01, effect_passed=False),
    )
    assert report.all_multiplicity_tests_accepted is True
    assert report.all_effects_accepted is False
    assert report.acceptance_passed is False


def test_family_requires_common_evidence_context_and_comparability() -> None:
    base = _report("a", p_value=0.01)
    other = _report("b", p_value=0.02)
    with pytest.raises(ValueError, match="measurement_source_id"):
        _family(base, replace(other, measurement_source_id="other-source"))
    with pytest.raises(ValueError, match="protocol"):
        _family(base, replace(other, protocol="other-protocol"))
    with pytest.raises(ValueError, match="machine_fingerprint"):
        _family(base, replace(other, machine_fingerprint="other-machine"))
    with pytest.raises(ValueError, match="reference_label"):
        _family(base, replace(other, reference_label="other-reference"))
    with pytest.raises(ValueError, match="universe size"):
        _family(base, replace(other, candidate_count=25))
    with pytest.raises(ValueError, match="top_k"):
        _family(base, replace(other, top_k=1))


def test_family_rejects_duplicate_normalized_ablation_labels() -> None:
    with pytest.raises(ValueError, match="distinct normalized"):
        _family(_report("Without-Beam", p_value=0.01), _report(" without-beam ", p_value=0.02))


def test_family_rejects_control_authority_and_incompatible_evidence_state() -> None:
    first = _report("a", p_value=0.01)
    second = _report("b", p_value=0.02)
    with pytest.raises(ValueError, match="automatic control"):
        _family(first, replace(second, automatic_control_allowed=True))
    with pytest.raises(ValueError, match="evidence_state"):
        _family(first, replace(second, evidence_state="UNVERIFIED_OTHER_METHOD"))
    assert first.evidence_state == ABLATION_EVIDENCE_STATE


def test_family_requires_declared_minimum_size_and_valid_alpha() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        _family(_report("only", p_value=0.01))
    with pytest.raises(ValueError, match="minimum_required_ablations"):
        _family(_report("a", p_value=0.01), _report("b", p_value=0.02), minimum_required_ablations=1)
    with pytest.raises(ValueError, match="in \\(0, 1\\]"):
        _family(family_wise_alpha=0.0)


def test_family_report_is_deterministic_for_identical_ordered_inputs() -> None:
    first = _family()
    second = _family()
    assert first == second
    assert first.as_dict() == second.as_dict()
