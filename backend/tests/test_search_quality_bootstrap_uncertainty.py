from __future__ import annotations

import pytest

from app.heldout_evaluation import HeldoutCandidateMeasurement
from app.search_quality_bootstrap_uncertainty import (
    EVIDENCE_STATE,
    evaluate_search_quality_bootstrap_uncertainty,
)
from app.search_quality_holdout import SearchQualityHoldoutEvidence


def _evidence(*, one_miss: bool = False, workload_count: int = 6) -> SearchQualityHoldoutEvidence:
    measurements: list[HeldoutCandidateMeasurement] = []
    for index in range(workload_count):
        workload_id = f"w{index + 1}"
        if one_miss and index == workload_count - 1:
            measurements.extend(
                (
                    HeldoutCandidateMeasurement(workload_id, "x", 1.0, 2.0),
                    HeldoutCandidateMeasurement(workload_id, "y", 2.0, 1.0),
                )
            )
        else:
            measurements.extend(
                (
                    HeldoutCandidateMeasurement(workload_id, "x", 1.0, 1.0),
                    HeldoutCandidateMeasurement(workload_id, "y", 2.0, 2.0),
                )
            )
    return SearchQualityHoldoutEvidence(
        measurement_source_id="uncertainty-heldout-a",
        protocol="rq-search-quality-v1",
        machine_fingerprint="machine-a",
        measurements=tuple(measurements),
    )


def _evaluate(evidence: SearchQualityHoldoutEvidence | None = None, **overrides: object):
    kwargs = {
        "model_development_source_ids": {"training-a", "calibration-a"},
        "minimum_required_workloads": 3,
        "top_k": 1,
        "minimum_allowed_oracle_hit_rate": 0.8,
        "minimum_allowed_mean_top_k_recall": 0.8,
        "maximum_allowed_mean_top1_regret_ratio": 0.2,
        "maximum_allowed_worst_top1_regret_ratio": 1.0,
        "bootstrap_rounds": 400,
        "bootstrap_seed": 17,
    }
    kwargs.update(overrides)
    return evaluate_search_quality_bootstrap_uncertainty(evidence or _evidence(), **kwargs)


def test_stable_evidence_passes_conservative_bootstrap_bounds_without_control_authority() -> None:
    report = _evaluate()
    assert report.point_acceptance_passed is True
    assert report.confidence_bound_acceptance_passed is True
    assert report.acceptance_passed is True
    assert report.oracle_hit_rate == 1.0
    assert report.oracle_hit_rate_ci95_low == 1.0
    assert report.oracle_hit_rate_ci95_high == 1.0
    assert report.mean_top_k_recall_ci95_low == 1.0
    assert report.mean_top1_regret_ratio_ci95_high == 0.0
    assert report.confidence_level == 0.95
    assert report.evidence_state == EVIDENCE_STATE
    assert report.automatic_control_allowed is False
    payload = report.as_dict()
    assert "workload-level" in payload["truth_boundary"]
    assert "representative" in payload["truth_boundary"]
    assert "production-control" in payload["truth_boundary"]


def test_point_estimate_can_pass_while_bootstrap_lower_bound_rejects_uncertainty() -> None:
    report = _evaluate(
        _evidence(one_miss=True),
        minimum_allowed_oracle_hit_rate=0.8,
        minimum_allowed_mean_top_k_recall=0.8,
        maximum_allowed_mean_top1_regret_ratio=0.2,
    )
    assert report.oracle_hit_rate == pytest.approx(5 / 6)
    assert report.point_acceptance_passed is True
    assert report.oracle_hit_rate_ci95_low < 0.8
    assert report.confidence_bound_acceptance_passed is False
    assert report.acceptance_passed is False


def test_uncertainty_gate_requires_at_least_three_workloads() -> None:
    with pytest.raises(ValueError, match="at least 3"):
        _evaluate(_evidence(workload_count=2), minimum_required_workloads=2)


def test_inherits_source_leakage_guard_from_heldout_gate() -> None:
    with pytest.raises(ValueError, match="overlaps model development"):
        _evaluate(model_development_source_ids={" uncertainty-heldout-a "})


def test_inherits_bootstrap_round_validation() -> None:
    with pytest.raises(ValueError, match="bootstrap_rounds must be at least 100"):
        _evaluate(bootstrap_rounds=99)


def test_caller_declared_regret_limit_remains_authoritative() -> None:
    report = _evaluate(
        _evidence(one_miss=True),
        minimum_allowed_oracle_hit_rate=0.0,
        minimum_allowed_mean_top_k_recall=0.0,
        maximum_allowed_mean_top1_regret_ratio=0.1,
        maximum_allowed_worst_top1_regret_ratio=1.0,
    )
    assert report.mean_top1_regret_ratio == pytest.approx(1 / 6)
    assert report.point_acceptance_passed is False
    assert report.acceptance_passed is False


def test_report_is_deterministic_for_identical_evidence_and_seed() -> None:
    assert _evaluate().as_dict() == _evaluate().as_dict()
