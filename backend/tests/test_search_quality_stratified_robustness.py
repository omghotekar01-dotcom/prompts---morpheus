from __future__ import annotations

import pytest

from app.heldout_evaluation import HeldoutCandidateMeasurement
from app.search_quality_holdout import SearchQualityHoldoutEvidence
from app.search_quality_stratified_robustness import (
    EVIDENCE_STATE,
    evaluate_search_quality_stratified_robustness,
)


def _evidence(*, family_b_miss: bool = False) -> SearchQualityHoldoutEvidence:
    measurements: list[HeldoutCandidateMeasurement] = []
    for workload_id in ("a1", "a2", "b1", "b2"):
        if family_b_miss and workload_id == "b2":
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
        measurement_source_id="stratified-heldout-a",
        protocol="rq-search-quality-v1",
        machine_fingerprint="machine-a",
        measurements=tuple(measurements),
    )


def _strata() -> dict[str, str]:
    return {"a1": "family-a", "a2": "family-a", "b1": "family-b", "b2": "family-b"}


def _evaluate(evidence: SearchQualityHoldoutEvidence | None = None, **overrides: object):
    kwargs = {
        "workload_strata": _strata(),
        "model_development_source_ids": {"training-a", "calibration-a"},
        "minimum_required_strata": 2,
        "minimum_workloads_per_stratum": 2,
        "top_k": 1,
        "minimum_allowed_oracle_hit_rate": 0.5,
        "minimum_allowed_mean_top_k_recall": 0.5,
        "maximum_allowed_mean_top1_regret_ratio": 0.51,
        "maximum_allowed_worst_top1_regret_ratio": 1.01,
        "max_allowed_oracle_hit_rate_spread": 0.5,
        "max_allowed_mean_top_k_recall_spread": 0.5,
        "max_allowed_mean_top1_regret_ratio_spread": 0.5,
        "max_allowed_worst_top1_regret_ratio_spread": 1.0,
        "bootstrap_rounds": 200,
        "bootstrap_seed": 7,
    }
    kwargs.update(overrides)
    return evaluate_search_quality_stratified_robustness(evidence or _evidence(), **kwargs)


def test_balanced_strata_pass_declared_limits_without_control_authority() -> None:
    report = _evaluate()
    assert report.acceptance_passed is True
    assert report.all_strata_acceptance_passed is True
    assert report.stratum_count == 2
    assert report.workload_count == 4
    assert report.candidate_count == 8
    assert report.oracle_hit_rate_spread == 0.0
    assert report.mean_top_k_recall_spread == 0.0
    assert report.mean_top1_regret_ratio_spread == 0.0
    assert report.worst_top1_regret_ratio_spread == 0.0
    assert report.evidence_state == EVIDENCE_STATE
    assert report.automatic_control_allowed is False
    payload = report.as_dict()
    assert "caller-predeclared" in payload["truth_boundary"]
    assert "representative" in payload["truth_boundary"]
    assert "production control" in payload["truth_boundary"]


def test_caller_declared_cross_stratum_spread_can_reject_internal_disparity() -> None:
    report = _evaluate(
        _evidence(family_b_miss=True),
        max_allowed_oracle_hit_rate_spread=0.25,
        max_allowed_mean_top_k_recall_spread=0.25,
    )
    assert report.all_strata_acceptance_passed is True
    assert report.oracle_hit_rate_spread == pytest.approx(0.5)
    assert report.mean_top_k_recall_spread == pytest.approx(0.5)
    assert report.acceptance_passed is False


def test_requires_exact_workload_to_stratum_coverage() -> None:
    missing = _strata()
    del missing["b2"]
    with pytest.raises(ValueError, match="exactly cover measured workloads"):
        _evaluate(workload_strata=missing)

    extra = _strata()
    extra["ghost"] = "family-c"
    with pytest.raises(ValueError, match="exactly cover measured workloads"):
        _evaluate(workload_strata=extra)


def test_rejects_whitespace_normalized_duplicate_workload_mapping() -> None:
    mapping = _strata()
    mapping[" a1 "] = "family-c"
    with pytest.raises(ValueError, match="duplicate workload IDs after normalization"):
        _evaluate(workload_strata=mapping)


def test_requires_multiple_strata_and_multiple_workloads_per_stratum() -> None:
    one_stratum = {key: "all" for key in _strata()}
    with pytest.raises(ValueError, match="at least 2 distinct strata"):
        _evaluate(workload_strata=one_stratum)

    thin = {"a1": "family-a", "a2": "family-a", "b1": "family-b", "b2": "family-c"}
    with pytest.raises(ValueError, match="at least 2 distinct workloads"):
        _evaluate(workload_strata=thin)


def test_inherits_source_leakage_guard_from_holdout_gate() -> None:
    with pytest.raises(ValueError, match="overlaps model development"):
        _evaluate(model_development_source_ids={" stratified-heldout-a "})


def test_rejects_invalid_declared_limits_and_minimums() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        _evaluate(max_allowed_oracle_hit_rate_spread=1.1)
    with pytest.raises(ValueError, match="non-negative"):
        _evaluate(max_allowed_mean_top1_regret_ratio_spread=-0.01)
    with pytest.raises(ValueError, match="minimum_required_strata must be at least 2"):
        _evaluate(minimum_required_strata=1)
    with pytest.raises(ValueError, match="minimum_workloads_per_stratum must be at least 2"):
        _evaluate(minimum_workloads_per_stratum=1)


def test_report_is_deterministic_for_identical_evidence_and_seed() -> None:
    assert _evaluate().as_dict() == _evaluate().as_dict()
