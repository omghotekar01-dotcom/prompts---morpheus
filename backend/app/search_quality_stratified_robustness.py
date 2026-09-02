from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping

from .heldout_evaluation import HeldoutCandidateMeasurement
from .search_quality_holdout import (
    SearchQualityHoldoutEvidence,
    evaluate_search_quality_holdout,
)

EVIDENCE_STATE = "METHODOLOGY_ONLY_CALLER_SUPPLIED_STRATIFIED_SEARCH_QUALITY_ROBUSTNESS"
TRUTH_BOUNDARY = (
    "This gate evaluates caller-supplied held-out candidate measurements across caller-predeclared "
    "workload strata. It requires complete, non-overlapping workload-to-stratum assignment, at least "
    "two workloads per stratum, reuses the held-out source-leakage/protocol/machine/top-k guards, and "
    "applies only caller-declared acceptance and cross-stratum disparity limits. A passing report shows "
    "internal consistency across the supplied strata only; it does not establish that the strata or "
    "workloads are representative, independently sampled, statistically independent, externally "
    "collected, publication-grade, superior to alternatives, novel, or authorized for production control."
)


@dataclass(frozen=True)
class SearchQualityStratumResult:
    stratum_id: str
    workload_count: int
    candidate_count: int
    oracle_hit_rate: float
    mean_top_k_recall: float
    mean_top1_regret_ratio: float
    worst_top1_regret_ratio: float
    acceptance_passed: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "stratum_id": self.stratum_id,
            "workload_count": self.workload_count,
            "candidate_count": self.candidate_count,
            "oracle_hit_rate": self.oracle_hit_rate,
            "mean_top_k_recall": self.mean_top_k_recall,
            "mean_top1_regret_ratio": self.mean_top1_regret_ratio,
            "worst_top1_regret_ratio": self.worst_top1_regret_ratio,
            "acceptance_passed": self.acceptance_passed,
        }


@dataclass(frozen=True)
class SearchQualityStratifiedRobustnessReport:
    measurement_source_id: str
    protocol: str
    machine_fingerprint: str
    stratum_count: int
    workload_count: int
    candidate_count: int
    top_k: int
    oracle_hit_rate_spread: float
    mean_top_k_recall_spread: float
    mean_top1_regret_ratio_spread: float
    worst_top1_regret_ratio_spread: float
    max_allowed_oracle_hit_rate_spread: float
    max_allowed_mean_top_k_recall_spread: float
    max_allowed_mean_top1_regret_ratio_spread: float
    max_allowed_worst_top1_regret_ratio_spread: float
    all_strata_acceptance_passed: bool
    acceptance_passed: bool
    strata: tuple[SearchQualityStratumResult, ...]
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "measurement_source_id": self.measurement_source_id,
            "protocol": self.protocol,
            "machine_fingerprint": self.machine_fingerprint,
            "stratum_count": self.stratum_count,
            "workload_count": self.workload_count,
            "candidate_count": self.candidate_count,
            "top_k": self.top_k,
            "oracle_hit_rate_spread": self.oracle_hit_rate_spread,
            "mean_top_k_recall_spread": self.mean_top_k_recall_spread,
            "mean_top1_regret_ratio_spread": self.mean_top1_regret_ratio_spread,
            "worst_top1_regret_ratio_spread": self.worst_top1_regret_ratio_spread,
            "max_allowed_oracle_hit_rate_spread": self.max_allowed_oracle_hit_rate_spread,
            "max_allowed_mean_top_k_recall_spread": self.max_allowed_mean_top_k_recall_spread,
            "max_allowed_mean_top1_regret_ratio_spread": self.max_allowed_mean_top1_regret_ratio_spread,
            "max_allowed_worst_top1_regret_ratio_spread": self.max_allowed_worst_top1_regret_ratio_spread,
            "all_strata_acceptance_passed": self.all_strata_acceptance_passed,
            "acceptance_passed": self.acceptance_passed,
            "strata": [item.as_dict() for item in self.strata],
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def _validate_rate(name: str, value: float) -> None:
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be finite and between 0 and 1")


def _validate_nonnegative(name: str, value: float) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and non-negative")


def _normalize_strata(
    measurements: tuple[HeldoutCandidateMeasurement, ...],
    workload_strata: Mapping[str, str],
) -> dict[str, str]:
    measured_workloads: dict[str, str] = {}
    for item in measurements:
        normalized = item.workload_id.strip()
        if not normalized:
            raise ValueError("measurement workload_id cannot be empty")
        previous = measured_workloads.setdefault(normalized, item.workload_id)
        if previous != item.workload_id:
            raise ValueError("measurement workload IDs collide after whitespace normalization")

    normalized_mapping: dict[str, str] = {}
    for raw_workload, raw_stratum in workload_strata.items():
        workload_id = raw_workload.strip()
        stratum_id = raw_stratum.strip()
        if not workload_id:
            raise ValueError("workload_strata contains an empty workload ID")
        if not stratum_id:
            raise ValueError("workload_strata contains an empty stratum ID")
        if workload_id in normalized_mapping:
            raise ValueError("workload_strata contains duplicate workload IDs after normalization")
        normalized_mapping[workload_id] = stratum_id

    measured_ids = set(measured_workloads)
    mapped_ids = set(normalized_mapping)
    if measured_ids != mapped_ids:
        missing = sorted(measured_ids - mapped_ids)
        extra = sorted(mapped_ids - measured_ids)
        raise ValueError(
            f"workload_strata must exactly cover measured workloads; missing={missing}, extra={extra}"
        )
    return normalized_mapping


def evaluate_search_quality_stratified_robustness(
    evidence: SearchQualityHoldoutEvidence,
    *,
    workload_strata: Mapping[str, str],
    model_development_source_ids: Iterable[str],
    minimum_required_strata: int = 2,
    minimum_workloads_per_stratum: int = 2,
    top_k: int = 3,
    minimum_allowed_oracle_hit_rate: float,
    minimum_allowed_mean_top_k_recall: float,
    maximum_allowed_mean_top1_regret_ratio: float,
    maximum_allowed_worst_top1_regret_ratio: float,
    max_allowed_oracle_hit_rate_spread: float,
    max_allowed_mean_top_k_recall_spread: float,
    max_allowed_mean_top1_regret_ratio_spread: float,
    max_allowed_worst_top1_regret_ratio_spread: float,
    bootstrap_rounds: int = 2000,
    bootstrap_seed: int = 1337,
) -> SearchQualityStratifiedRobustnessReport:
    """Evaluate predeclared workload-stratum robustness under caller-declared limits.

    Strata are metadata supplied by the caller. This function checks coverage and
    internal metric consistency; it cannot establish population representativeness.
    """

    if minimum_required_strata < 2:
        raise ValueError("minimum_required_strata must be at least 2")
    if minimum_workloads_per_stratum < 2:
        raise ValueError("minimum_workloads_per_stratum must be at least 2")
    _validate_rate("max_allowed_oracle_hit_rate_spread", max_allowed_oracle_hit_rate_spread)
    _validate_rate("max_allowed_mean_top_k_recall_spread", max_allowed_mean_top_k_recall_spread)
    _validate_nonnegative(
        "max_allowed_mean_top1_regret_ratio_spread",
        max_allowed_mean_top1_regret_ratio_spread,
    )
    _validate_nonnegative(
        "max_allowed_worst_top1_regret_ratio_spread",
        max_allowed_worst_top1_regret_ratio_spread,
    )

    evidence.validate()
    strata_by_workload = _normalize_strata(evidence.measurements, workload_strata)
    stratum_ids = tuple(sorted(set(strata_by_workload.values())))
    if len(stratum_ids) < minimum_required_strata:
        raise ValueError(
            f"stratified evidence must contain at least {minimum_required_strata} distinct strata"
        )

    development_sources = tuple(model_development_source_ids)
    results: list[SearchQualityStratumResult] = []
    for stratum_id in stratum_ids:
        selected = tuple(
            item
            for item in evidence.measurements
            if strata_by_workload[item.workload_id.strip()] == stratum_id
        )
        workload_count = len({item.workload_id.strip() for item in selected})
        if workload_count < minimum_workloads_per_stratum:
            raise ValueError(
                f"stratum {stratum_id!r} must contain at least "
                f"{minimum_workloads_per_stratum} distinct workloads"
            )
        stratum_evidence = SearchQualityHoldoutEvidence(
            measurement_source_id=evidence.measurement_source_id,
            protocol=evidence.protocol,
            machine_fingerprint=evidence.machine_fingerprint,
            measurements=selected,
        )
        report = evaluate_search_quality_holdout(
            stratum_evidence,
            model_development_source_ids=development_sources,
            minimum_required_workloads=minimum_workloads_per_stratum,
            top_k=top_k,
            minimum_allowed_oracle_hit_rate=minimum_allowed_oracle_hit_rate,
            minimum_allowed_mean_top_k_recall=minimum_allowed_mean_top_k_recall,
            maximum_allowed_mean_top1_regret_ratio=maximum_allowed_mean_top1_regret_ratio,
            maximum_allowed_worst_top1_regret_ratio=maximum_allowed_worst_top1_regret_ratio,
            bootstrap_rounds=bootstrap_rounds,
            bootstrap_seed=bootstrap_seed,
        )
        results.append(
            SearchQualityStratumResult(
                stratum_id=stratum_id,
                workload_count=report.workload_count,
                candidate_count=report.candidate_count,
                oracle_hit_rate=report.oracle_hit_rate,
                mean_top_k_recall=report.mean_top_k_recall,
                mean_top1_regret_ratio=report.mean_top1_regret_ratio,
                worst_top1_regret_ratio=report.worst_top1_regret_ratio,
                acceptance_passed=report.acceptance_passed,
            )
        )

    def spread(values: list[float]) -> float:
        return max(values) - min(values)

    oracle_spread = spread([item.oracle_hit_rate for item in results])
    recall_spread = spread([item.mean_top_k_recall for item in results])
    mean_regret_spread = spread([item.mean_top1_regret_ratio for item in results])
    worst_regret_spread = spread([item.worst_top1_regret_ratio for item in results])
    all_strata_accepted = all(item.acceptance_passed for item in results)
    accepted = (
        all_strata_accepted
        and oracle_spread <= max_allowed_oracle_hit_rate_spread
        and recall_spread <= max_allowed_mean_top_k_recall_spread
        and mean_regret_spread <= max_allowed_mean_top1_regret_ratio_spread
        and worst_regret_spread <= max_allowed_worst_top1_regret_ratio_spread
    )

    return SearchQualityStratifiedRobustnessReport(
        measurement_source_id=evidence.measurement_source_id.strip(),
        protocol=evidence.protocol.strip(),
        machine_fingerprint=evidence.machine_fingerprint.strip(),
        stratum_count=len(results),
        workload_count=len(strata_by_workload),
        candidate_count=len(evidence.measurements),
        top_k=top_k,
        oracle_hit_rate_spread=oracle_spread,
        mean_top_k_recall_spread=recall_spread,
        mean_top1_regret_ratio_spread=mean_regret_spread,
        worst_top1_regret_ratio_spread=worst_regret_spread,
        max_allowed_oracle_hit_rate_spread=max_allowed_oracle_hit_rate_spread,
        max_allowed_mean_top_k_recall_spread=max_allowed_mean_top_k_recall_spread,
        max_allowed_mean_top1_regret_ratio_spread=max_allowed_mean_top1_regret_ratio_spread,
        max_allowed_worst_top1_regret_ratio_spread=max_allowed_worst_top1_regret_ratio_spread,
        all_strata_acceptance_passed=all_strata_accepted,
        acceptance_passed=accepted,
        strata=tuple(results),
    )
