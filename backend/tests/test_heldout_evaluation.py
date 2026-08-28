from __future__ import annotations

import pytest

from app.heldout_evaluation import HeldoutCandidateMeasurement, evaluate_heldout_candidate_groups


def _fixture() -> list[HeldoutCandidateMeasurement]:
    return [
        HeldoutCandidateMeasurement("w1", "a", 1.0, 1.1),
        HeldoutCandidateMeasurement("w1", "b", 2.0, 2.2),
        HeldoutCandidateMeasurement("w1", "c", 3.0, 3.4),
        HeldoutCandidateMeasurement("w2", "a", 1.0, 3.0),
        HeldoutCandidateMeasurement("w2", "b", 1.5, 1.0),
        HeldoutCandidateMeasurement("w2", "c", 2.0, 2.0),
    ]


def test_grouped_heldout_evaluation_preserves_workload_decisions() -> None:
    report = evaluate_heldout_candidate_groups(
        _fixture(),
        top_k=2,
        bootstrap_rounds=500,
        bootstrap_seed=7,
    )
    assert report.workload_count == 2
    assert report.candidate_count == 6
    assert report.oracle_hit_rate == 0.5
    assert report.mean_top1_regret_abs == 1.0
    assert report.median_top1_regret_abs == 1.0
    assert report.mean_top_k_recall == 0.75
    assert report.regret_mean_ci95_low <= report.mean_top1_regret_abs <= report.regret_mean_ci95_high
    assert [item.workload_id for item in report.workloads] == ["w1", "w2"]
    payload = report.as_dict()
    assert payload["evidence_state"] == "HELDOUT_EVALUATION_CALLER_SUPPLIED_MEASUREMENTS"
    assert "caller-supplied" in payload["truth_note"]


def test_grouped_evaluation_is_bootstrap_deterministic_for_same_seed() -> None:
    first = evaluate_heldout_candidate_groups(_fixture(), bootstrap_rounds=300, bootstrap_seed=99)
    second = evaluate_heldout_candidate_groups(_fixture(), bootstrap_rounds=300, bootstrap_seed=99)
    assert first.as_dict() == second.as_dict()


def test_grouped_evaluation_rejects_duplicate_candidate_identity() -> None:
    bad = [
        HeldoutCandidateMeasurement("w", "same", 1.0, 1.0),
        HeldoutCandidateMeasurement("w", "same", 2.0, 2.0),
    ]
    with pytest.raises(ValueError, match="duplicate candidate_id"):
        evaluate_heldout_candidate_groups(bad)


def test_grouped_evaluation_rejects_singleton_workload() -> None:
    with pytest.raises(ValueError, match="at least two"):
        evaluate_heldout_candidate_groups(
            [HeldoutCandidateMeasurement("only", "a", 1.0, 1.0)]
        )
