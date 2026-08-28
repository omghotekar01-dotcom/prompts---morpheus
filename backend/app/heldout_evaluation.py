from __future__ import annotations

import math
import random
import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .research import PredictionPoint, evaluate_predictions


@dataclass(frozen=True)
class HeldoutCandidateMeasurement:
    workload_id: str
    candidate_id: str
    predicted: float
    measured: float

    def validate(self) -> None:
        if not self.workload_id:
            raise ValueError("workload_id cannot be empty")
        if not self.candidate_id:
            raise ValueError("candidate_id cannot be empty")
        if not math.isfinite(self.predicted) or not math.isfinite(self.measured):
            raise ValueError("predicted and measured costs must be finite")
        if self.predicted < 0 or self.measured < 0:
            raise ValueError("predicted and measured costs must be non-negative")


@dataclass(frozen=True)
class WorkloadRankingEvaluation:
    workload_id: str
    candidate_count: int
    oracle_hit: bool
    model_selected_candidate: str
    oracle_candidate: str
    top1_regret_abs: float
    top1_regret_ratio: float | None
    top_k: int
    top_k_recall: float
    spearman_rho: float | None
    kendall_tau_b: float | None
    mae: float
    rmse: float

    def as_dict(self) -> dict[str, object]:
        return {
            "workload_id": self.workload_id,
            "candidate_count": self.candidate_count,
            "oracle_hit": self.oracle_hit,
            "model_selected_candidate": self.model_selected_candidate,
            "oracle_candidate": self.oracle_candidate,
            "top1_regret_abs": self.top1_regret_abs,
            "top1_regret_ratio": self.top1_regret_ratio,
            "top_k": self.top_k,
            "top_k_recall": self.top_k_recall,
            "spearman_rho": self.spearman_rho,
            "kendall_tau_b": self.kendall_tau_b,
            "mae": self.mae,
            "rmse": self.rmse,
        }


@dataclass(frozen=True)
class HeldoutEvaluationReport:
    workload_count: int
    candidate_count: int
    top_k: int
    oracle_hit_rate: float
    mean_top_k_recall: float
    mean_top1_regret_abs: float
    median_top1_regret_abs: float
    mean_top1_regret_ratio: float | None
    mean_spearman_rho: float | None
    mean_kendall_tau_b: float | None
    mean_mae: float
    mean_rmse: float
    regret_mean_ci95_low: float
    regret_mean_ci95_high: float
    bootstrap_rounds: int
    bootstrap_seed: int
    workloads: tuple[WorkloadRankingEvaluation, ...]
    evidence_state: str = "HELDOUT_EVALUATION_CALLER_SUPPLIED_MEASUREMENTS"

    def as_dict(self) -> dict[str, object]:
        return {
            "workload_count": self.workload_count,
            "candidate_count": self.candidate_count,
            "top_k": self.top_k,
            "oracle_hit_rate": self.oracle_hit_rate,
            "mean_top_k_recall": self.mean_top_k_recall,
            "mean_top1_regret_abs": self.mean_top1_regret_abs,
            "median_top1_regret_abs": self.median_top1_regret_abs,
            "mean_top1_regret_ratio": self.mean_top1_regret_ratio,
            "mean_spearman_rho": self.mean_spearman_rho,
            "mean_kendall_tau_b": self.mean_kendall_tau_b,
            "mean_mae": self.mean_mae,
            "mean_rmse": self.mean_rmse,
            "regret_mean_ci95_low": self.regret_mean_ci95_low,
            "regret_mean_ci95_high": self.regret_mean_ci95_high,
            "bootstrap_rounds": self.bootstrap_rounds,
            "bootstrap_seed": self.bootstrap_seed,
            "workloads": [item.as_dict() for item in self.workloads],
            "evidence_state": self.evidence_state,
            "truth_note": (
                "MORPHEUS evaluates only caller-supplied held-out measurements here; this report does not establish "
                "that the measurements were collected independently, fairly, or on publication-grade hardware."
            ),
        }


def _mean_optional(values: Iterable[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return sum(present) / len(present) if present else None


def _percentile(sorted_values: list[float], fraction: float) -> float:
    if not sorted_values:
        raise ValueError("percentile requires at least one value")
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = fraction * (len(sorted_values) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def _bootstrap_mean_ci95(values: list[float], *, rounds: int, seed: int) -> tuple[float, float]:
    if not values:
        raise ValueError("bootstrap requires at least one value")
    if rounds < 100:
        raise ValueError("bootstrap_rounds must be at least 100")
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(rounds):
        sample = [values[rng.randrange(len(values))] for _ in values]
        means.append(sum(sample) / len(sample))
    means.sort()
    return _percentile(means, 0.025), _percentile(means, 0.975)


def evaluate_heldout_candidate_groups(
    measurements: Iterable[HeldoutCandidateMeasurement],
    *,
    top_k: int = 3,
    bootstrap_rounds: int = 2000,
    bootstrap_seed: int = 1337,
) -> HeldoutEvaluationReport:
    """Evaluate cost-model ranking quality across independent workload groups.

    Each workload group is treated as one selection decision: lower cost is
    better, predicted ranking selects a candidate, and measured ranking defines
    the empirical oracle within the supplied candidate set. The evaluator keeps
    per-workload results instead of pooling all candidates, preventing large
    candidate spaces from silently dominating small ones.
    """

    if top_k < 1:
        raise ValueError("top_k must be positive")
    items = list(measurements)
    if not items:
        raise ValueError("at least one held-out measurement is required")
    for item in items:
        item.validate()

    grouped: dict[str, list[HeldoutCandidateMeasurement]] = defaultdict(list)
    for item in items:
        grouped[item.workload_id].append(item)

    workload_results: list[WorkloadRankingEvaluation] = []
    for workload_id in sorted(grouped):
        candidates = grouped[workload_id]
        if len(candidates) < 2:
            raise ValueError(f"workload {workload_id!r} must contain at least two candidate measurements")
        candidate_ids = [item.candidate_id for item in candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError(f"workload {workload_id!r} contains duplicate candidate_id values")

        evaluation = evaluate_predictions(
            PredictionPoint(item.candidate_id, item.predicted, item.measured) for item in candidates
        )
        effective_k = min(top_k, len(candidates))
        predicted_top = {
            item.candidate_id
            for item in sorted(candidates, key=lambda item: (item.predicted, item.candidate_id))[:effective_k]
        }
        measured_top = {
            item.candidate_id
            for item in sorted(candidates, key=lambda item: (item.measured, item.candidate_id))[:effective_k]
        }
        top_k_recall = len(predicted_top & measured_top) / effective_k
        workload_results.append(
            WorkloadRankingEvaluation(
                workload_id=workload_id,
                candidate_count=len(candidates),
                oracle_hit=evaluation.selected_by_model == evaluation.oracle_best,
                model_selected_candidate=evaluation.selected_by_model,
                oracle_candidate=evaluation.oracle_best,
                top1_regret_abs=evaluation.top1_regret_abs,
                top1_regret_ratio=evaluation.top1_regret_ratio,
                top_k=effective_k,
                top_k_recall=top_k_recall,
                spearman_rho=evaluation.spearman_rho,
                kendall_tau_b=evaluation.kendall_tau_b,
                mae=evaluation.mae,
                rmse=evaluation.rmse,
            )
        )

    regrets = [item.top1_regret_abs for item in workload_results]
    ci_low, ci_high = _bootstrap_mean_ci95(regrets, rounds=bootstrap_rounds, seed=bootstrap_seed)
    return HeldoutEvaluationReport(
        workload_count=len(workload_results),
        candidate_count=len(items),
        top_k=top_k,
        oracle_hit_rate=sum(1 for item in workload_results if item.oracle_hit) / len(workload_results),
        mean_top_k_recall=sum(item.top_k_recall for item in workload_results) / len(workload_results),
        mean_top1_regret_abs=sum(regrets) / len(regrets),
        median_top1_regret_abs=statistics.median(regrets),
        mean_top1_regret_ratio=_mean_optional(item.top1_regret_ratio for item in workload_results),
        mean_spearman_rho=_mean_optional(item.spearman_rho for item in workload_results),
        mean_kendall_tau_b=_mean_optional(item.kendall_tau_b for item in workload_results),
        mean_mae=sum(item.mae for item in workload_results) / len(workload_results),
        mean_rmse=sum(item.rmse for item in workload_results) / len(workload_results),
        regret_mean_ci95_low=ci_low,
        regret_mean_ci95_high=ci_high,
        bootstrap_rounds=bootstrap_rounds,
        bootstrap_seed=bootstrap_seed,
        workloads=tuple(workload_results),
    )
