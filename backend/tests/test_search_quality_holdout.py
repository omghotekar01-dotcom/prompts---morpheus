from __future__ import annotations

import pytest

from app.heldout_evaluation import HeldoutCandidateMeasurement
from app.search_quality_holdout import (
    EVIDENCE_STATE,
    SearchQualityHoldoutEvidence,
    evaluate_search_quality_holdout,
)


def _evidence() -> SearchQualityHoldoutEvidence:
    return SearchQualityHoldoutEvidence(
        measurement_source_id="heldout-batch-2026-09-a",
        protocol="rq3-hardware-v1",
        machine_fingerprint="machine-a",
        measurements=(
            HeldoutCandidateMeasurement("w1", "a", 1.0, 1.0),
            HeldoutCandidateMeasurement("w1", "b", 2.0, 2.0),
            HeldoutCandidateMeasurement("w1", "c", 3.0, 3.0),
            HeldoutCandidateMeasurement("w2", "a", 1.0, 1.2),
            HeldoutCandidateMeasurement("w2", "b", 2.0, 1.0),
            HeldoutCandidateMeasurement("w2", "c", 3.0, 3.0),
        ),
    )


def _evaluate(
    evidence: SearchQualityHoldoutEvidence | None = None,
    **overrides: object,
):
    kwargs = {
        "model_development_source_ids": {"training-a", "calibration-a"},
        "minimum_required_workloads": 2,
        "top_k": 2,
        "minimum_allowed_oracle_hit_rate": 0.5,
        "minimum_allowed_mean_top_k_recall": 0.75,
        "maximum_allowed_mean_top1_regret_ratio": 0.11,
        "maximum_allowed_worst_top1_regret_ratio": 0.21,
        "bootstrap_rounds": 200,
        "bootstrap_seed": 7,
    }
    kwargs.update(overrides)
    return evaluate_search_quality_holdout(evidence or _evidence(), **kwargs)


def test_declared_holdout_limits_pass_without_granting_control_authority() -> None:
    report = _evaluate()
    assert report.acceptance_passed is True
    assert report.workload_count == 2
    assert report.top_k == 2
    assert report.oracle_hit_rate == 0.5
    assert report.mean_top_k_recall == 1.0
    assert report.mean_top1_regret_ratio == pytest.approx(0.1)
    assert report.worst_top1_regret_ratio == pytest.approx(0.2)
    assert report.evidence_state == EVIDENCE_STATE
    assert report.automatic_control_allowed is False
    payload = report.as_dict()
    assert payload["top_k"] == 2
    assert "caller-supplied" in payload["truth_boundary"]
    assert "unlike ranking cutoffs" in payload["truth_boundary"]
    assert "superiority" in payload["truth_boundary"]


def test_tighter_caller_declared_regret_limit_fails_acceptance() -> None:
    report = _evaluate(maximum_allowed_mean_top1_regret_ratio=0.09)
    assert report.acceptance_passed is False


def test_rejects_model_development_source_leakage() -> None:
    with pytest.raises(ValueError, match="overlaps model development"):
        _evaluate(model_development_source_ids={"heldout-batch-2026-09-a"})


def test_rejects_source_leakage_after_whitespace_normalization() -> None:
    base = _evidence()
    evidence = SearchQualityHoldoutEvidence(
        measurement_source_id="  heldout-batch-2026-09-a  ",
        protocol=base.protocol,
        machine_fingerprint=base.machine_fingerprint,
        measurements=base.measurements,
    )
    with pytest.raises(ValueError, match="overlaps model development"):
        _evaluate(evidence, model_development_source_ids={"heldout-batch-2026-09-a"})


def test_rejects_insufficient_distinct_workload_coverage() -> None:
    evidence = SearchQualityHoldoutEvidence(
        measurement_source_id="heldout-one",
        protocol="rq3-hardware-v1",
        machine_fingerprint="machine-a",
        measurements=(
            HeldoutCandidateMeasurement("only", "a", 1.0, 1.0),
            HeldoutCandidateMeasurement("only", "b", 2.0, 2.0),
        ),
    )
    with pytest.raises(ValueError, match="at least 2 distinct workloads"):
        _evaluate(evidence)


def test_rejects_zero_measured_cost_where_relative_regret_is_undefined() -> None:
    evidence = SearchQualityHoldoutEvidence(
        measurement_source_id="heldout-zero",
        protocol="rq3-hardware-v1",
        machine_fingerprint="machine-a",
        measurements=(
            HeldoutCandidateMeasurement("w1", "a", 1.0, 0.0),
            HeldoutCandidateMeasurement("w1", "b", 2.0, 2.0),
            HeldoutCandidateMeasurement("w2", "a", 1.0, 1.0),
            HeldoutCandidateMeasurement("w2", "b", 2.0, 2.0),
        ),
    )
    with pytest.raises(ValueError, match="must be positive"):
        _evaluate(evidence)


def test_rejects_invalid_caller_thresholds_and_top_k() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        _evaluate(minimum_allowed_oracle_hit_rate=1.1)
    with pytest.raises(ValueError, match="non-negative"):
        _evaluate(maximum_allowed_worst_top1_regret_ratio=-0.1)
    with pytest.raises(ValueError, match="top_k must be at least 1"):
        _evaluate(top_k=0)


def test_report_is_deterministic_for_identical_evidence_and_seed() -> None:
    assert _evaluate().as_dict() == _evaluate().as_dict()
