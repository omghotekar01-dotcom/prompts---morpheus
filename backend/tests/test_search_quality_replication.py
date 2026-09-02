from __future__ import annotations

from dataclasses import replace

import pytest

from app.heldout_evaluation import HeldoutCandidateMeasurement
from app.search_quality_holdout import (
    SearchQualityHoldoutEvidence,
    evaluate_search_quality_holdout,
)
from app.search_quality_replication import (
    EVIDENCE_STATE,
    evaluate_search_quality_replication,
)


def _holdout(source: str, machine: str, *, measured_b: float = 1.0, top_k: int = 2):
    evidence = SearchQualityHoldoutEvidence(
        measurement_source_id=source,
        protocol="rq3-hardware-v1",
        machine_fingerprint=machine,
        measurements=(
            HeldoutCandidateMeasurement("w1", "a", 1.0, 1.0),
            HeldoutCandidateMeasurement("w1", "b", 2.0, 2.0),
            HeldoutCandidateMeasurement("w2", "a", 1.0, 1.2),
            HeldoutCandidateMeasurement("w2", "b", 2.0, measured_b),
        ),
    )
    return evaluate_search_quality_holdout(
        evidence,
        model_development_source_ids={"training-a", "calibration-a"},
        minimum_required_workloads=2,
        top_k=top_k,
        minimum_allowed_oracle_hit_rate=0.5,
        minimum_allowed_mean_top_k_recall=1.0,
        maximum_allowed_mean_top1_regret_ratio=0.11,
        maximum_allowed_worst_top1_regret_ratio=0.21,
        bootstrap_rounds=100,
        bootstrap_seed=7,
    )


def _evaluate(reports=None, **overrides: object):
    items = reports or (
        _holdout("heldout-a", "machine-a"),
        _holdout("heldout-b", "machine-b"),
    )
    kwargs = {
        "max_allowed_oracle_hit_rate_spread": 0.0,
        "max_allowed_mean_top_k_recall_spread": 0.0,
        "max_allowed_mean_top1_regret_ratio_spread": 0.0,
        "max_allowed_worst_top1_regret_ratio_spread": 0.0,
        "minimum_distinct_sources": 2,
        "minimum_distinct_machines": 2,
    }
    kwargs.update(overrides)
    return evaluate_search_quality_replication(items, **kwargs)


def test_declared_replication_limits_pass_without_granting_control_authority() -> None:
    report = _evaluate()
    assert report.source_count == 2
    assert report.machine_count == 2
    assert report.top_k == 2
    assert report.mean_machine_top_k_recall == 1.0
    assert report.mean_top_k_recall_spread == 0.0
    assert report.replication_passed is True
    assert report.all_holdouts_accepted is True
    assert report.evidence_state == EVIDENCE_STATE
    assert report.automatic_control_allowed is False
    payload = report.as_dict()
    assert payload["top_k"] == 2
    assert "one ranking cutoff" in payload["truth_boundary"]
    assert "do not prove independent" in payload["truth_boundary"]
    assert "superiority" in payload["truth_boundary"]


def test_tighter_caller_declared_spread_limit_can_fail_replication() -> None:
    first = _holdout("heldout-a", "machine-a")
    second = replace(
        _holdout("heldout-b", "machine-b"),
        oracle_hit_rate=0.6,
    )
    report = _evaluate(
        (first, second),
        max_allowed_oracle_hit_rate_spread=0.05,
        max_allowed_mean_top_k_recall_spread=1.0,
        max_allowed_mean_top1_regret_ratio_spread=1.0,
        max_allowed_worst_top1_regret_ratio_spread=1.0,
    )
    assert report.oracle_hit_rate_spread == pytest.approx(0.1)
    assert report.replication_passed is False


def test_tighter_top_k_recall_spread_can_fail_replication() -> None:
    first = _holdout("heldout-a", "machine-a")
    second = replace(_holdout("heldout-b", "machine-b"), mean_top_k_recall=0.9)
    report = _evaluate(
        (first, second),
        max_allowed_oracle_hit_rate_spread=1.0,
        max_allowed_mean_top_k_recall_spread=0.05,
        max_allowed_mean_top1_regret_ratio_spread=1.0,
        max_allowed_worst_top1_regret_ratio_spread=1.0,
    )
    assert report.mean_top_k_recall_spread == pytest.approx(0.1)
    assert report.replication_passed is False


def test_rejects_mismatched_top_k_before_comparing_recall() -> None:
    first = _holdout("heldout-a", "machine-a", top_k=2)
    second = replace(_holdout("heldout-b", "machine-b", top_k=2), top_k=3)
    with pytest.raises(ValueError, match="one top_k ranking cutoff"):
        _evaluate((first, second))


def test_rejects_duplicate_source_after_whitespace_normalization() -> None:
    first = _holdout("heldout-a", "machine-a")
    second = replace(
        _holdout("heldout-b", "machine-b"),
        measurement_source_id="  heldout-a  ",
    )
    with pytest.raises(ValueError, match="normalized measurement source"):
        _evaluate((first, second))


def test_rejects_duplicate_machine_after_whitespace_normalization() -> None:
    first = _holdout("heldout-a", "machine-a")
    second = replace(
        _holdout("heldout-b", "machine-b"),
        machine_fingerprint=" machine-a ",
    )
    with pytest.raises(ValueError, match="normalized machine fingerprint"):
        _evaluate((first, second))


def test_rejects_mixed_protocols_and_acceptance_policies() -> None:
    first = _holdout("heldout-a", "machine-a")
    mixed_protocol = replace(_holdout("heldout-b", "machine-b"), protocol="rq3-hardware-v2")
    with pytest.raises(ValueError, match="one measurement protocol"):
        _evaluate((first, mixed_protocol))

    mixed_policy = replace(
        _holdout("heldout-b", "machine-b"),
        maximum_allowed_mean_top1_regret_ratio=0.2,
    )
    with pytest.raises(ValueError, match="one declared holdout acceptance policy"):
        _evaluate((first, mixed_policy))


def test_rejects_failed_holdout_or_attempted_control_authority() -> None:
    first = _holdout("heldout-a", "machine-a")
    failed = replace(_holdout("heldout-b", "machine-b"), acceptance_passed=False)
    with pytest.raises(ValueError, match="must satisfy"):
        _evaluate((first, failed))

    control = replace(_holdout("heldout-b", "machine-b"), automatic_control_allowed=True)
    with pytest.raises(ValueError, match="cannot authorize automatic control"):
        _evaluate((first, control))


def test_rejects_invalid_evidence_state_and_invalid_caller_threshold() -> None:
    first = _holdout("heldout-a", "machine-a")
    wrong_state = replace(_holdout("heldout-b", "machine-b"), evidence_state="OTHER")
    with pytest.raises(ValueError, match="only P24"):
        _evaluate((first, wrong_state))

    with pytest.raises(ValueError, match="finite and non-negative"):
        _evaluate(max_allowed_mean_top_k_recall_spread=-0.01)


def test_report_is_deterministic_for_identical_reports() -> None:
    reports = (
        _holdout("heldout-a", "machine-a"),
        _holdout("heldout-b", "machine-b"),
    )
    assert _evaluate(reports).as_dict() == _evaluate(reports).as_dict()
