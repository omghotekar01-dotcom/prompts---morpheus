from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class PredictionPoint:
    """One cost-model prediction paired with an externally measured value.

    MORPHEUS treats lower values as better for this evaluator (for example
    latency, build time, memory, or an aggregate objective). The evaluator does
    not manufacture measurements; callers must supply measured values produced
    by an external benchmark protocol.
    """

    label: str
    predicted: float
    measured: float

    def validate(self) -> None:
        if not self.label:
            raise ValueError("prediction point label cannot be empty")
        if not math.isfinite(self.predicted) or not math.isfinite(self.measured):
            raise ValueError("prediction and measurement values must be finite")
        if self.predicted < 0 or self.measured < 0:
            raise ValueError("cost values must be non-negative")


@dataclass(frozen=True)
class PredictionEvaluation:
    sample_count: int
    mae: float
    rmse: float
    mape: float | None
    signed_bias: float
    spearman_rho: float | None
    kendall_tau_b: float | None
    selected_by_model: str
    oracle_best: str
    selected_predicted: float
    selected_measured: float
    oracle_measured: float
    top1_regret_abs: float
    top1_regret_ratio: float | None
    worst_absolute_error: float
    evidence_state: str = "EVALUATED_AGAINST_CALLER_SUPPLIED_MEASUREMENTS"

    def as_dict(self) -> dict[str, object]:
        return {
            "sample_count": self.sample_count,
            "mae": self.mae,
            "rmse": self.rmse,
            "mape": self.mape,
            "signed_bias": self.signed_bias,
            "spearman_rho": self.spearman_rho,
            "kendall_tau_b": self.kendall_tau_b,
            "selected_by_model": self.selected_by_model,
            "oracle_best": self.oracle_best,
            "selected_predicted": self.selected_predicted,
            "selected_measured": self.selected_measured,
            "oracle_measured": self.oracle_measured,
            "top1_regret_abs": self.top1_regret_abs,
            "top1_regret_ratio": self.top1_regret_ratio,
            "worst_absolute_error": self.worst_absolute_error,
            "evidence_state": self.evidence_state,
        }


def _average_ranks(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(indexed):
        end = cursor + 1
        while end < len(indexed) and indexed[end][1] == indexed[cursor][1]:
            end += 1
        average_rank = (cursor + 1 + end) / 2.0
        for position in range(cursor, end):
            ranks[indexed[position][0]] = average_rank
        cursor = end
    return ranks


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right, strict=True))
    left_energy = sum((a - left_mean) ** 2 for a in left)
    right_energy = sum((b - right_mean) ** 2 for b in right)
    denominator = math.sqrt(left_energy * right_energy)
    if denominator == 0:
        return None
    return numerator / denominator


def _spearman(predicted: list[float], measured: list[float]) -> float | None:
    return _pearson(_average_ranks(predicted), _average_ranks(measured))


def _kendall_tau_b(predicted: list[float], measured: list[float]) -> float | None:
    if len(predicted) != len(measured) or len(predicted) < 2:
        return None

    concordant = 0
    discordant = 0
    ties_predicted = 0
    ties_measured = 0

    for i in range(len(predicted) - 1):
        for j in range(i + 1, len(predicted)):
            pred_delta = predicted[i] - predicted[j]
            measured_delta = measured[i] - measured[j]
            if pred_delta == 0 and measured_delta == 0:
                continue
            if pred_delta == 0:
                ties_predicted += 1
                continue
            if measured_delta == 0:
                ties_measured += 1
                continue
            if pred_delta * measured_delta > 0:
                concordant += 1
            else:
                discordant += 1

    denominator = math.sqrt(
        (concordant + discordant + ties_predicted)
        * (concordant + discordant + ties_measured)
    )
    if denominator == 0:
        return None
    return (concordant - discordant) / denominator


def evaluate_predictions(points: Iterable[PredictionPoint]) -> PredictionEvaluation:
    """Evaluate prediction quality without conflating predictions with evidence.

    The caller provides paired predictions and benchmark measurements. MORPHEUS
    then reports absolute error, ranking quality, and decision regret. This is a
    P10 research primitive intended for held-out cost-model evaluation.
    """

    items = list(points)
    if len(items) < 2:
        raise ValueError("at least two prediction points are required")
    for item in items:
        item.validate()

    predicted = [item.predicted for item in items]
    measured = [item.measured for item in items]
    errors = [prediction - observation for prediction, observation in zip(predicted, measured, strict=True)]
    absolute_errors = [abs(error) for error in errors]

    mae = sum(absolute_errors) / len(items)
    rmse = math.sqrt(sum(error * error for error in errors) / len(items))
    nonzero_relative_errors = [
        abs(prediction - observation) / observation
        for prediction, observation in zip(predicted, measured, strict=True)
        if observation != 0
    ]
    mape = (
        sum(nonzero_relative_errors) / len(nonzero_relative_errors)
        if nonzero_relative_errors
        else None
    )
    signed_bias = sum(errors) / len(items)

    selected_index = min(range(len(items)), key=lambda index: (items[index].predicted, items[index].label))
    oracle_index = min(range(len(items)), key=lambda index: (items[index].measured, items[index].label))
    selected = items[selected_index]
    oracle = items[oracle_index]
    regret_abs = max(0.0, selected.measured - oracle.measured)
    regret_ratio = regret_abs / oracle.measured if oracle.measured > 0 else None

    return PredictionEvaluation(
        sample_count=len(items),
        mae=mae,
        rmse=rmse,
        mape=mape,
        signed_bias=signed_bias,
        spearman_rho=_spearman(predicted, measured),
        kendall_tau_b=_kendall_tau_b(predicted, measured),
        selected_by_model=selected.label,
        oracle_best=oracle.label,
        selected_predicted=selected.predicted,
        selected_measured=selected.measured,
        oracle_measured=oracle.measured,
        top1_regret_abs=regret_abs,
        top1_regret_ratio=regret_ratio,
        worst_absolute_error=max(absolute_errors),
    )
