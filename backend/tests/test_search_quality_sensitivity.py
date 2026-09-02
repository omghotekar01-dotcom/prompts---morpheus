from __future__ import annotations

import pytest

from app.heldout_evaluation import HeldoutCandidateMeasurement
from app.search_quality_holdout import SearchQualityHoldoutEvidence
from app.search_quality_sensitivity import (
    EVIDENCE_STATE,
    evaluate_search_quality_sensitivity,
)


def _evidence(*, one_miss: bool = False) -> SearchQualityHoldoutEvidence:
    measurements: list[HeldoutCandidateMeasurement] = []
    for workload_id in ("w1", "w2", "w3"):
        if one_miss and workload_id == "w3":
            measurements.extend(
                (
                    HeldoutCandidateMeasurement(workload_id, "a", 1.0, 2.0),
                    HeldoutCandidateMeasurement(workload_id, "b", 2.0, 1.0),
                )
            )
        else:
            measurements.extend(
                (
                    HeldoutCandidateMeasurement(workload_id, "a", 1.0, 1.0),
                    HeldoutCandidateMeasurement(workload_id, "b", 2.0, 2.0),
                )
            )
    return SearchQualityHoldoutEvidence(
        measurement_source_id="heldout-sensitivity-a",
        protocol="rq-search-quality-v1",
        machine_fingerprint="machine-a",
        measurements=tuple(measurements),
    )


def _evaluate(
    evidence: SearchQualityHoldoutEvidence | None = None,
    **overrides: object,
):
    kwargs = {
        "model_development_source_ids": {"training-a", "calibration-a"},
        "minimum_required_workloads": 3,
        "top_k": 1,
        "minimum_allowed_oracle_hit_rate": 0.5,
        "minimum_allowed_mean_top_k_recall": 0.5,
        "maximum_allowed_mean_top1_regret_ratio": 0.51,
        "maximum_allowed_worst_top1_regret_ratio": 1.01,
        "max_allowed_oracle_hit_rate_drop": 0.2,
        "max_allowed_mean_top_k_recall_drop": 0.2,
        "max_allowed_mean_top1_regret_ratio_increase": 0.2,
        "max_allowed_worst_top1_regret_ratio_increase": 0.2,
        "bootstrap_rounds": 200,
        "bootstrap_seed": 7,
    }
    kwargs.update(overrides)
    return evaluate_search_quality_sensitivity(evidence or _evidence(), **kwargs)


def test_stable_holdout_passes_declared_sensitivity_limits_without_control_authority() -> None:
    report = _evaluate()
    assert report.acceptance_passed is True
    assert report.all_leave_one_out_acceptance_passed is True
    assert report.workload_count == 3
    assert len(report.leave_one_out) == 3
    assert report.maximum_oracle_hit_rate_drop == 0.0
    assert report.maximum_mean_top_k_recall_drop == 0.0
    assert report.maximum_mean_top1_regret_ratio_increase == 0.0
    assert report.maximum_worst_top1_regret_ratio_increase == 0.0
    assert report.evidence_state == EVIDENCE_STATE
    assert report.automatic_control_allowed is False
    payload = report.as_dict()
    assert "leave-one-workload-out" in payload["truth_boundary"]
    assert "caller-supplied" in payload["truth_boundary"]
    assert "superiority" in payload["truth_boundary"]


def test_caller_declared_oracle_stability_limit_can_reject_fragile_aggregate() -> None:
    report = _evaluate(
        _evidence(one_miss=True),
        max_allowed_oracle_hit_rate_drop=0.1,
        max_allowed_mean_top_k_recall_drop=0.2,
    )
    assert report.baseline_oracle_hit_rate == pytest.approx(2.0 / 3.0)
    assert report.maximum_oracle_hit_rate_drop == pytest.approx(1.0 / 6.0)
    assert report.all_leave_one_out_acceptance_passed is True
    assert report.acceptance_passed is False


def test_caller_declared_recall_stability_limit_is_bound_separately() -> None:
    report = _evaluate(
        _evidence(one_miss=True),
        max_allowed_oracle_hit_rate_drop=0.2,
        max_allowed_mean_top_k_recall_drop=0.1,
    )
    assert report.maximum_mean_top_k_recall_drop == pytest.approx(1.0 / 6.0)
    assert report.acceptance_passed is False


def test_rejects_less_than_three_workloads_for_sensitivity() -> None:
    evidence = SearchQualityHoldoutEvidence(
        measurement_source_id="heldout-two",
        protocol="rq-search-quality-v1",
        machine_fingerprint="machine-a",
        measurements=(
            HeldoutCandidateMeasurement("w1", "a", 1.0, 1.0),
            HeldoutCandidateMeasurement("w1", "b", 2.0, 2.0),
            HeldoutCandidateMeasurement("w2", "a", 1.0, 1.0),
            HeldoutCandidateMeasurement("w2", "b", 2.0, 2.0),
        ),
    )
    with pytest.raises(ValueError, match="at least 3 distinct workloads"):
        _evaluate(evidence)


def test_rejects_model_development_source_leakage_via_holdout_gate() -> None:
    with pytest.raises(ValueError, match="overlaps model development"):
        _evaluate(model_development_source_ids={" heldout-sensitivity-a "})


def test_rejects_invalid_sensitivity_limits_and_minimum_workload_count() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        _evaluate(max_allowed_oracle_hit_rate_drop=1.1)
    with pytest.raises(ValueError, match="non-negative"):
        _evaluate(max_allowed_mean_top1_regret_ratio_increase=-0.01)
    with pytest.raises(ValueError, match="must be at least 3"):
        _evaluate(minimum_required_workloads=2)


def test_report_is_deterministic_for_identical_evidence_and_seed() -> None:
    assert _evaluate().as_dict() == _evaluate().as_dict()
