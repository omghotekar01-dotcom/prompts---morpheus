from __future__ import annotations

import pytest

from app.heldout_evaluation import HeldoutCandidateMeasurement
from app.search_quality_ablation import EVIDENCE_STATE, evaluate_paired_search_quality_ablation
from app.search_quality_holdout import SearchQualityHoldoutEvidence


def _paired(*, workloads: int = 4, changed_measurement: bool = False):
    reference: list[HeldoutCandidateMeasurement] = []
    ablated: list[HeldoutCandidateMeasurement] = []
    for index in range(workloads):
        workload_id = f"w{index + 1}"
        measured_x = 1.0
        measured_y = 2.0
        reference.extend(
            (
                HeldoutCandidateMeasurement(workload_id, "x", 1.0, measured_x),
                HeldoutCandidateMeasurement(workload_id, "y", 2.0, measured_y),
            )
        )
        ablated.extend(
            (
                HeldoutCandidateMeasurement(workload_id, "x", 2.0, measured_x + (0.5 if changed_measurement and index == 0 else 0.0)),
                HeldoutCandidateMeasurement(workload_id, "y", 1.0, measured_y),
            )
        )
    kwargs = dict(measurement_source_id="paired-heldout-a", protocol="rq-ablation-v1", machine_fingerprint="machine-a")
    return SearchQualityHoldoutEvidence(measurements=tuple(reference), **kwargs), SearchQualityHoldoutEvidence(measurements=tuple(ablated), **kwargs)


def _evaluate(reference=None, ablated=None, **overrides):
    if reference is None or ablated is None:
        reference, ablated = _paired()
    kwargs = {
        "reference_label": "full-model",
        "ablated_label": "without-calibration-feature",
        "model_development_source_ids": {"training-a", "calibration-a"},
        "minimum_required_workloads": 4,
        "top_k": 1,
        "minimum_required_mean_regret_ratio_improvement": 0.5,
        "maximum_allowed_one_sided_p_value": 0.1,
        "randomization_rounds": 2000,
        "randomization_seed": 17,
    }
    kwargs.update(overrides)
    return evaluate_paired_search_quality_ablation(reference, ablated, **kwargs)


def test_paired_ablation_reports_effect_and_exact_randomization_without_control_authority() -> None:
    report = _evaluate()
    assert report.reference_mean_top1_regret_ratio == 0.0
    assert report.ablated_mean_top1_regret_ratio == 1.0
    assert report.mean_regret_ratio_improvement == 1.0
    assert report.improved_workload_count == 4
    assert report.tied_workload_count == 0
    assert report.worsened_workload_count == 0
    assert report.randomization_method == "exact_sign_flip"
    assert report.randomization_rounds == 16
    assert report.one_sided_p_value == pytest.approx(1 / 16)
    assert report.effect_acceptance_passed is True
    assert report.statistical_acceptance_passed is True
    assert report.acceptance_passed is True
    assert report.evidence_state == EVIDENCE_STATE
    assert report.automatic_control_allowed is False
    payload = report.as_dict()
    assert "causal attribution" in payload["truth_boundary"]
    assert "publication-grade" in payload["truth_boundary"]
    assert "production-control" in payload["truth_boundary"]


def test_caller_declared_effect_threshold_can_reject_same_evidence() -> None:
    report = _evaluate(minimum_required_mean_regret_ratio_improvement=1.1)
    assert report.effect_acceptance_passed is False
    assert report.statistical_acceptance_passed is True
    assert report.acceptance_passed is False


def test_caller_declared_p_value_limit_can_reject_same_evidence() -> None:
    report = _evaluate(maximum_allowed_one_sided_p_value=0.05)
    assert report.effect_acceptance_passed is True
    assert report.statistical_acceptance_passed is False
    assert report.acceptance_passed is False


def test_paired_conditions_must_share_exact_measured_costs() -> None:
    reference, ablated = _paired(changed_measurement=True)
    with pytest.raises(ValueError, match="identical measured costs"):
        _evaluate(reference, ablated)


def test_paired_conditions_must_share_candidate_universe() -> None:
    reference, ablated = _paired()
    ablated = SearchQualityHoldoutEvidence(
        measurement_source_id=ablated.measurement_source_id,
        protocol=ablated.protocol,
        machine_fingerprint=ablated.machine_fingerprint,
        measurements=ablated.measurements[:-1],
    )
    with pytest.raises(ValueError, match="exact workload/candidate universe"):
        _evaluate(reference, ablated)


def test_inherits_heldout_source_leakage_guard() -> None:
    with pytest.raises(ValueError, match="overlaps model development"):
        _evaluate(model_development_source_ids={" paired-heldout-a "})


def test_requires_declared_condition_identity_and_distinct_labels() -> None:
    with pytest.raises(ValueError, match="must differ"):
        _evaluate(reference_label="same", ablated_label="same")
    with pytest.raises(ValueError, match="cannot be empty"):
        _evaluate(reference_label="   ")


def test_rejects_invalid_acceptance_limits() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        _evaluate(minimum_required_mean_regret_ratio_improvement=-0.1)
    with pytest.raises(ValueError, match="in \\(0, 1\\]"):
        _evaluate(maximum_allowed_one_sided_p_value=0.0)


def test_requires_minimum_workload_coverage() -> None:
    reference, ablated = _paired(workloads=3)
    with pytest.raises(ValueError, match="at least 4"):
        _evaluate(reference, ablated)


def test_report_is_deterministic_for_identical_inputs() -> None:
    first = _evaluate()
    second = _evaluate()
    assert first == second
    assert first.as_dict() == second.as_dict()
