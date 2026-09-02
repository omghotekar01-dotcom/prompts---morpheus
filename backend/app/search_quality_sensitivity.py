from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from .heldout_evaluation import HeldoutCandidateMeasurement
from .search_quality_holdout import (
    SearchQualityHoldoutEvidence,
    SearchQualityHoldoutValidationReport,
    evaluate_search_quality_holdout,
)

EVIDENCE_STATE = "METHODOLOGY_ONLY_CALLER_SUPPLIED_SEARCH_QUALITY_SENSITIVITY"
TRUTH_BOUNDARY = (
    "This gate performs deterministic leave-one-workload-out sensitivity analysis over the same "
    "caller-supplied held-out candidate measurements used by the search-quality holdout gate. It "
    "inherits source-leakage, protocol, machine, top-k, and caller-declared acceptance-policy guards, "
    "then measures how much aggregate decision quality changes when each workload is removed. A "
    "passing report does not establish independent measurement collection, workload representativeness, "
    "instrumentation validity, statistical independence, publication-grade robustness, search or "
    "performance superiority, novelty, or production authorization."
)


@dataclass(frozen=True)
class LeaveOneWorkloadOutResult:
    omitted_workload_id: str
    oracle_hit_rate: float
    mean_top_k_recall: float
    mean_top1_regret_ratio: float
    worst_top1_regret_ratio: float
    acceptance_passed: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "omitted_workload_id": self.omitted_workload_id,
            "oracle_hit_rate": self.oracle_hit_rate,
            "mean_top_k_recall": self.mean_top_k_recall,
            "mean_top1_regret_ratio": self.mean_top1_regret_ratio,
            "worst_top1_regret_ratio": self.worst_top1_regret_ratio,
            "acceptance_passed": self.acceptance_passed,
        }


@dataclass(frozen=True)
class SearchQualitySensitivityReport:
    measurement_source_id: str
    protocol: str
    machine_fingerprint: str
    workload_count: int
    candidate_count: int
    top_k: int
    baseline_oracle_hit_rate: float
    baseline_mean_top_k_recall: float
    baseline_mean_top1_regret_ratio: float
    baseline_worst_top1_regret_ratio: float
    maximum_oracle_hit_rate_drop: float
    maximum_mean_top_k_recall_drop: float
    maximum_mean_top1_regret_ratio_increase: float
    maximum_worst_top1_regret_ratio_increase: float
    max_allowed_oracle_hit_rate_drop: float
    max_allowed_mean_top_k_recall_drop: float
    max_allowed_mean_top1_regret_ratio_increase: float
    max_allowed_worst_top1_regret_ratio_increase: float
    all_leave_one_out_acceptance_passed: bool
    acceptance_passed: bool
    leave_one_out: tuple[LeaveOneWorkloadOutResult, ...]
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
            "baseline_oracle_hit_rate": self.baseline_oracle_hit_rate,
            "baseline_mean_top_k_recall": self.baseline_mean_top_k_recall,
            "baseline_mean_top1_regret_ratio": self.baseline_mean_top1_regret_ratio,
            "baseline_worst_top1_regret_ratio": self.baseline_worst_top1_regret_ratio,
            "maximum_oracle_hit_rate_drop": self.maximum_oracle_hit_rate_drop,
            "maximum_mean_top_k_recall_drop": self.maximum_mean_top_k_recall_drop,
            "maximum_mean_top1_regret_ratio_increase": self.maximum_mean_top1_regret_ratio_increase,
            "maximum_worst_top1_regret_ratio_increase": self.maximum_worst_top1_regret_ratio_increase,
            "max_allowed_oracle_hit_rate_drop": self.max_allowed_oracle_hit_rate_drop,
            "max_allowed_mean_top_k_recall_drop": self.max_allowed_mean_top_k_recall_drop,
            "max_allowed_mean_top1_regret_ratio_increase": self.max_allowed_mean_top1_regret_ratio_increase,
            "max_allowed_worst_top1_regret_ratio_increase": self.max_allowed_worst_top1_regret_ratio_increase,
            "all_leave_one_out_acceptance_passed": self.all_leave_one_out_acceptance_passed,
            "acceptance_passed": self.acceptance_passed,
            "leave_one_out": [item.as_dict() for item in self.leave_one_out],
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


def _workload_ids(measurements: tuple[HeldoutCandidateMeasurement, ...]) -> tuple[str, ...]:
    return tuple(sorted({item.workload_id for item in measurements}))


def evaluate_search_quality_sensitivity(
    evidence: SearchQualityHoldoutEvidence,
    *,
    model_development_source_ids: Iterable[str],
    minimum_required_workloads: int = 3,
    top_k: int = 3,
    minimum_allowed_oracle_hit_rate: float,
    minimum_allowed_mean_top_k_recall: float,
    maximum_allowed_mean_top1_regret_ratio: float,
    maximum_allowed_worst_top1_regret_ratio: float,
    max_allowed_oracle_hit_rate_drop: float,
    max_allowed_mean_top_k_recall_drop: float,
    max_allowed_mean_top1_regret_ratio_increase: float,
    max_allowed_worst_top1_regret_ratio_increase: float,
    bootstrap_rounds: int = 2000,
    bootstrap_seed: int = 1337,
) -> SearchQualitySensitivityReport:
    """Evaluate leave-one-workload-out stability under caller-declared limits.

    This is a robustness methodology over one supplied holdout set, not an
    independent replication or a claim that the supplied workloads are
    representative of a wider population.
    """

    if minimum_required_workloads < 3:
        raise ValueError("minimum_required_workloads must be at least 3 for leave-one-out sensitivity")
    _validate_rate("max_allowed_oracle_hit_rate_drop", max_allowed_oracle_hit_rate_drop)
    _validate_rate("max_allowed_mean_top_k_recall_drop", max_allowed_mean_top_k_recall_drop)
    _validate_nonnegative(
        "max_allowed_mean_top1_regret_ratio_increase",
        max_allowed_mean_top1_regret_ratio_increase,
    )
    _validate_nonnegative(
        "max_allowed_worst_top1_regret_ratio_increase",
        max_allowed_worst_top1_regret_ratio_increase,
    )

    development_sources = tuple(model_development_source_ids)
    baseline: SearchQualityHoldoutValidationReport = evaluate_search_quality_holdout(
        evidence,
        model_development_source_ids=development_sources,
        minimum_required_workloads=minimum_required_workloads,
        top_k=top_k,
        minimum_allowed_oracle_hit_rate=minimum_allowed_oracle_hit_rate,
        minimum_allowed_mean_top_k_recall=minimum_allowed_mean_top_k_recall,
        maximum_allowed_mean_top1_regret_ratio=maximum_allowed_mean_top1_regret_ratio,
        maximum_allowed_worst_top1_regret_ratio=maximum_allowed_worst_top1_regret_ratio,
        bootstrap_rounds=bootstrap_rounds,
        bootstrap_seed=bootstrap_seed,
    )

    workload_ids = _workload_ids(evidence.measurements)
    if len(workload_ids) < minimum_required_workloads:
        raise ValueError(
            f"sensitivity evidence must contain at least {minimum_required_workloads} distinct workloads"
        )

    leave_one_out: list[LeaveOneWorkloadOutResult] = []
    reduced_minimum = max(2, minimum_required_workloads - 1)
    for workload_id in workload_ids:
        reduced_evidence = SearchQualityHoldoutEvidence(
            measurement_source_id=evidence.measurement_source_id,
            protocol=evidence.protocol,
            machine_fingerprint=evidence.machine_fingerprint,
            measurements=tuple(
                item for item in evidence.measurements if item.workload_id != workload_id
            ),
        )
        reduced = evaluate_search_quality_holdout(
            reduced_evidence,
            model_development_source_ids=development_sources,
            minimum_required_workloads=reduced_minimum,
            top_k=top_k,
            minimum_allowed_oracle_hit_rate=minimum_allowed_oracle_hit_rate,
            minimum_allowed_mean_top_k_recall=minimum_allowed_mean_top_k_recall,
            maximum_allowed_mean_top1_regret_ratio=maximum_allowed_mean_top1_regret_ratio,
            maximum_allowed_worst_top1_regret_ratio=maximum_allowed_worst_top1_regret_ratio,
            bootstrap_rounds=bootstrap_rounds,
            bootstrap_seed=bootstrap_seed,
        )
        leave_one_out.append(
            LeaveOneWorkloadOutResult(
                omitted_workload_id=workload_id,
                oracle_hit_rate=reduced.oracle_hit_rate,
                mean_top_k_recall=reduced.mean_top_k_recall,
                mean_top1_regret_ratio=reduced.mean_top1_regret_ratio,
                worst_top1_regret_ratio=reduced.worst_top1_regret_ratio,
                acceptance_passed=reduced.acceptance_passed,
            )
        )

    maximum_oracle_drop = max(
        0.0,
        max(baseline.oracle_hit_rate - item.oracle_hit_rate for item in leave_one_out),
    )
    maximum_recall_drop = max(
        0.0,
        max(baseline.mean_top_k_recall - item.mean_top_k_recall for item in leave_one_out),
    )
    maximum_mean_regret_increase = max(
        0.0,
        max(
            item.mean_top1_regret_ratio - baseline.mean_top1_regret_ratio
            for item in leave_one_out
        ),
    )
    maximum_worst_regret_increase = max(
        0.0,
        max(
            item.worst_top1_regret_ratio - baseline.worst_top1_regret_ratio
            for item in leave_one_out
        ),
    )
    all_reduced_accepted = all(item.acceptance_passed for item in leave_one_out)
    accepted = (
        baseline.acceptance_passed
        and all_reduced_accepted
        and maximum_oracle_drop <= max_allowed_oracle_hit_rate_drop
        and maximum_recall_drop <= max_allowed_mean_top_k_recall_drop
        and maximum_mean_regret_increase <= max_allowed_mean_top1_regret_ratio_increase
        and maximum_worst_regret_increase <= max_allowed_worst_top1_regret_ratio_increase
    )

    return SearchQualitySensitivityReport(
        measurement_source_id=baseline.measurement_source_id,
        protocol=baseline.protocol,
        machine_fingerprint=baseline.machine_fingerprint,
        workload_count=baseline.workload_count,
        candidate_count=baseline.candidate_count,
        top_k=baseline.top_k,
        baseline_oracle_hit_rate=baseline.oracle_hit_rate,
        baseline_mean_top_k_recall=baseline.mean_top_k_recall,
        baseline_mean_top1_regret_ratio=baseline.mean_top1_regret_ratio,
        baseline_worst_top1_regret_ratio=baseline.worst_top1_regret_ratio,
        maximum_oracle_hit_rate_drop=maximum_oracle_drop,
        maximum_mean_top_k_recall_drop=maximum_recall_drop,
        maximum_mean_top1_regret_ratio_increase=maximum_mean_regret_increase,
        maximum_worst_top1_regret_ratio_increase=maximum_worst_regret_increase,
        max_allowed_oracle_hit_rate_drop=max_allowed_oracle_hit_rate_drop,
        max_allowed_mean_top_k_recall_drop=max_allowed_mean_top_k_recall_drop,
        max_allowed_mean_top1_regret_ratio_increase=max_allowed_mean_top1_regret_ratio_increase,
        max_allowed_worst_top1_regret_ratio_increase=max_allowed_worst_top1_regret_ratio_increase,
        all_leave_one_out_acceptance_passed=all_reduced_accepted,
        acceptance_passed=accepted,
        leave_one_out=tuple(leave_one_out),
    )
