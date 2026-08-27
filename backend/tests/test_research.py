from __future__ import annotations

import math

import pytest

from app.research import PredictionPoint, evaluate_predictions


def test_prediction_evaluation_reports_perfect_ranking_and_zero_regret() -> None:
    evaluation = evaluate_predictions(
        [
            PredictionPoint("a", predicted=1.0, measured=1.2),
            PredictionPoint("b", predicted=2.0, measured=2.1),
            PredictionPoint("c", predicted=3.0, measured=2.9),
        ]
    )

    assert evaluation.sample_count == 3
    assert evaluation.selected_by_model == "a"
    assert evaluation.oracle_best == "a"
    assert evaluation.top1_regret_abs == 0
    assert evaluation.top1_regret_ratio == 0
    assert evaluation.spearman_rho == pytest.approx(1.0)
    assert evaluation.kendall_tau_b == pytest.approx(1.0)
    assert evaluation.evidence_state == "EVALUATED_AGAINST_CALLER_SUPPLIED_MEASUREMENTS"


def test_prediction_evaluation_exposes_ranking_failure_and_decision_regret() -> None:
    evaluation = evaluate_predictions(
        [
            PredictionPoint("model_pick", predicted=1.0, measured=9.0),
            PredictionPoint("middle", predicted=2.0, measured=5.0),
            PredictionPoint("oracle", predicted=3.0, measured=2.0),
        ]
    )

    assert evaluation.selected_by_model == "model_pick"
    assert evaluation.oracle_best == "oracle"
    assert evaluation.top1_regret_abs == pytest.approx(7.0)
    assert evaluation.top1_regret_ratio == pytest.approx(3.5)
    assert evaluation.spearman_rho == pytest.approx(-1.0)
    assert evaluation.kendall_tau_b == pytest.approx(-1.0)


def test_prediction_evaluation_handles_zero_measurement_without_fake_mape() -> None:
    evaluation = evaluate_predictions(
        [
            PredictionPoint("zero", predicted=0.3, measured=0.0),
            PredictionPoint("nonzero", predicted=1.5, measured=1.0),
        ]
    )

    assert evaluation.mape == pytest.approx(0.5)
    assert math.isfinite(evaluation.mae)
    assert evaluation.top1_regret_ratio is None


def test_prediction_evaluation_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="at least two"):
        evaluate_predictions([PredictionPoint("only", predicted=1.0, measured=1.0)])

    with pytest.raises(ValueError, match="non-negative"):
        evaluate_predictions(
            [
                PredictionPoint("bad", predicted=-1.0, measured=1.0),
                PredictionPoint("good", predicted=1.0, measured=1.0),
            ]
        )
