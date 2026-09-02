from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Iterable

from .heldout_evaluation import HeldoutEvaluationReport, evaluate_heldout_candidate_groups
from .search_quality_holdout import (
    SearchQualityHoldoutEvidence,
    SearchQualityHoldoutValidationReport,
    evaluate_search_quality_holdout,
)

EVIDENCE_STATE = "METHODOLOGY_ONLY_CALLER_SUPPLIED_SEARCH_QUALITY_BOOTSTRAP_UNCERTAINTY"
TRUTH_BOUNDARY = (
    "This gate adds deterministic workload-level percentile-bootstrap uncertainty analysis to caller-supplied "
    "held-out search-quality evidence. It first requires the existing held-out point-estimate gate to pass, then "
    "checks conservative 95% bootstrap bounds for oracle-hit rate, top-k recall, and mean relative top-1 regret "
    "against the same caller-declared acceptance limits. Workloads, not candidates, are resampled so candidate-rich "
    "workloads cannot silently dominate uncertainty estimates. A passing report is conditional on the supplied "
    "workload sample and bootstrap procedure; it does not establish representative or independent sampling, "
    "bootstrap coverage validity for the deployment population, independent measurement collection, publication-"
    "grade evidence, superiority, novelty, patentability, or production-control authorization."
)


@dataclass(frozen=True)
class SearchQualityBootstrapUncertaintyReport:
    measurement_source_id: str
    protocol: str
    machine_fingerprint: str
    workload_count: int
    candidate_count: int
    top_k: int
    bootstrap_rounds: int
    bootstrap_seed: int
    confidence_level: float
    oracle_hit_rate: float
    oracle_hit_rate_ci95_low: float
    oracle_hit_rate_ci95_high: float
    mean_top_k_recall: float
    mean_top_k_recall_ci95_low: float
    mean_top_k_recall_ci95_high: float
    mean_top1_regret_ratio: float
    mean_top1_regret_ratio_ci95_low: float
    mean_top1_regret_ratio_ci95_high: float
    worst_top1_regret_ratio: float
    minimum_allowed_oracle_hit_rate: float
    minimum_allowed_mean_top_k_recall: float
    maximum_allowed_mean_top1_regret_ratio: float
    maximum_allowed_worst_top1_regret_ratio: float
    point_acceptance_passed: bool
    confidence_bound_acceptance_passed: bool
    acceptance_passed: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "measurement_source_id": self.measurement_source_id,
            "protocol": self.protocol,
            "machine_fingerprint": self.machine_fingerprint,
            "workload_count": self.workload_count,
            "candidate_count": self.candidate_count,
            "top_k": self.top_k,
            "bootstrap_rounds": self.bootstrap_rounds,
            "bootstrap_seed": self.bootstrap_seed,
            "confidence_level": self.confidence_level,
            "oracle_hit_rate": self.oracle_hit_rate,
            "oracle_hit_rate_ci95_low": self.oracle_hit_rate_ci95_low,
            "oracle_hit_rate_ci95_high": self.oracle_hit_rate_ci95_high,
            "mean_top_k_recall": self.mean_top_k_recall,
            "mean_top_k_recall_ci95_low": self.mean_top_k_recall_ci95_low,
            "mean_top_k_recall_ci95_high": self.mean_top_k_recall_ci95_high,
            "mean_top1_regret_ratio": self.mean_top1_regret_ratio,
            "mean_top1_regret_ratio_ci95_low": self.mean_top1_regret_ratio_ci95_low,
            "mean_top1_regret_ratio_ci95_high": self.mean_top1_regret_ratio_ci95_high,
            "worst_top1_regret_ratio": self.worst_top1_regret_ratio,
            "minimum_allowed_oracle_hit_rate": self.minimum_allowed_oracle_hit_rate,
            "minimum_allowed_mean_top_k_recall": self.minimum_allowed_mean_top_k_recall,
            "maximum_allowed_mean_top1_regret_ratio": self.maximum_allowed_mean_top1_regret_ratio,
            "maximum_allowed_worst_top1_regret_ratio": self.maximum_allowed_worst_top1_regret_ratio,
            "point_acceptance_passed": self.point_acceptance_passed,
            "confidence_bound_acceptance_passed": self.confidence_bound_acceptance_passed,
            "acceptance_passed": self.acceptance_passed,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


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


def _workload_bootstrap_ci95(
    metrics: HeldoutEvaluationReport,
    *,
    rounds: int,
    seed: int,
) -> dict[str, tuple[float, float]]:
    if rounds < 100:
        raise ValueError("bootstrap_rounds must be at least 100")
    workloads = metrics.workloads
    if len(workloads) < 3:
        raise ValueError("uncertainty validation requires at least 3 distinct workloads")

    ratios = [item.top1_regret_ratio for item in workloads]
    if any(value is None for value in ratios):
        raise ValueError("relative search regret must be defined for every held-out workload")

    rng = random.Random(seed)
    oracle_samples: list[float] = []
    recall_samples: list[float] = []
    regret_samples: list[float] = []
    count = len(workloads)
    for _ in range(rounds):
        sample = [workloads[rng.randrange(count)] for _ in range(count)]
        oracle_samples.append(sum(1.0 if item.oracle_hit else 0.0 for item in sample) / count)
        recall_samples.append(sum(item.top_k_recall for item in sample) / count)
        sample_regrets = [float(item.top1_regret_ratio) for item in sample if item.top1_regret_ratio is not None]
        regret_samples.append(sum(sample_regrets) / count)

    intervals: dict[str, tuple[float, float]] = {}
    for name, values in (
        ("oracle_hit_rate", oracle_samples),
        ("mean_top_k_recall", recall_samples),
        ("mean_top1_regret_ratio", regret_samples),
    ):
        values.sort()
        intervals[name] = (_percentile(values, 0.025), _percentile(values, 0.975))
    return intervals


def evaluate_search_quality_bootstrap_uncertainty(
    evidence: SearchQualityHoldoutEvidence,
    *,
    model_development_source_ids: Iterable[str],
    minimum_required_workloads: int = 3,
    top_k: int = 3,
    minimum_allowed_oracle_hit_rate: float,
    minimum_allowed_mean_top_k_recall: float,
    maximum_allowed_mean_top1_regret_ratio: float,
    maximum_allowed_worst_top1_regret_ratio: float,
    bootstrap_rounds: int = 2000,
    bootstrap_seed: int = 1337,
) -> SearchQualityBootstrapUncertaintyReport:
    """Require point-estimate acceptance and conservative workload-bootstrap bounds.

    The 95% percentile interval is a deterministic analysis of the supplied workload
    sample. It is not promoted to a population-level confidence guarantee.
    """

    if minimum_required_workloads < 3:
        raise ValueError("minimum_required_workloads must be at least 3 for uncertainty validation")

    point: SearchQualityHoldoutValidationReport = evaluate_search_quality_holdout(
        evidence,
        model_development_source_ids=model_development_source_ids,
        minimum_required_workloads=minimum_required_workloads,
        top_k=top_k,
        minimum_allowed_oracle_hit_rate=minimum_allowed_oracle_hit_rate,
        minimum_allowed_mean_top_k_recall=minimum_allowed_mean_top_k_recall,
        maximum_allowed_mean_top1_regret_ratio=maximum_allowed_mean_top1_regret_ratio,
        maximum_allowed_worst_top1_regret_ratio=maximum_allowed_worst_top1_regret_ratio,
        bootstrap_rounds=bootstrap_rounds,
        bootstrap_seed=bootstrap_seed,
    )

    metrics = evaluate_heldout_candidate_groups(
        evidence.measurements,
        top_k=top_k,
        bootstrap_rounds=bootstrap_rounds,
        bootstrap_seed=bootstrap_seed,
    )
    intervals = _workload_bootstrap_ci95(metrics, rounds=bootstrap_rounds, seed=bootstrap_seed)

    oracle_low, oracle_high = intervals["oracle_hit_rate"]
    recall_low, recall_high = intervals["mean_top_k_recall"]
    regret_low, regret_high = intervals["mean_top1_regret_ratio"]

    confidence_bound_accepted = (
        oracle_low >= minimum_allowed_oracle_hit_rate
        and recall_low >= minimum_allowed_mean_top_k_recall
        and regret_high <= maximum_allowed_mean_top1_regret_ratio
    )
    accepted = point.acceptance_passed and confidence_bound_accepted

    return SearchQualityBootstrapUncertaintyReport(
        measurement_source_id=point.measurement_source_id,
        protocol=point.protocol,
        machine_fingerprint=point.machine_fingerprint,
        workload_count=point.workload_count,
        candidate_count=point.candidate_count,
        top_k=point.top_k,
        bootstrap_rounds=bootstrap_rounds,
        bootstrap_seed=bootstrap_seed,
        confidence_level=0.95,
        oracle_hit_rate=point.oracle_hit_rate,
        oracle_hit_rate_ci95_low=oracle_low,
        oracle_hit_rate_ci95_high=oracle_high,
        mean_top_k_recall=point.mean_top_k_recall,
        mean_top_k_recall_ci95_low=recall_low,
        mean_top_k_recall_ci95_high=recall_high,
        mean_top1_regret_ratio=point.mean_top1_regret_ratio,
        mean_top1_regret_ratio_ci95_low=regret_low,
        mean_top1_regret_ratio_ci95_high=regret_high,
        worst_top1_regret_ratio=point.worst_top1_regret_ratio,
        minimum_allowed_oracle_hit_rate=point.minimum_allowed_oracle_hit_rate,
        minimum_allowed_mean_top_k_recall=point.minimum_allowed_mean_top_k_recall,
        maximum_allowed_mean_top1_regret_ratio=point.maximum_allowed_mean_top1_regret_ratio,
        maximum_allowed_worst_top1_regret_ratio=point.maximum_allowed_worst_top1_regret_ratio,
        point_acceptance_passed=point.acceptance_passed,
        confidence_bound_acceptance_passed=confidence_bound_accepted,
        acceptance_passed=accepted,
    )
