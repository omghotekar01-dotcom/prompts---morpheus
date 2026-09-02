from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from .heldout_evaluation import (
    HeldoutCandidateMeasurement,
    HeldoutEvaluationReport,
    evaluate_heldout_candidate_groups,
)

EVIDENCE_STATE = "METHODOLOGY_ONLY_CALLER_SUPPLIED_HELDOUT_SEARCH_QUALITY"
TRUTH_BOUNDARY = (
    "This gate evaluates caller-supplied held-out candidate measurements under an explicitly identified "
    "measurement protocol and machine fingerprint, with source-leakage and minimum-workload guards, and "
    "applies only caller-declared acceptance limits. The evaluated top_k is bound into the report so recall "
    "comparisons cannot silently mix unlike ranking cutoffs. A passing report does not establish independent "
    "measurement collection, instrumentation validity, publication-grade evidence, universal search or "
    "performance superiority, novelty, or production authorization."
)


@dataclass(frozen=True)
class SearchQualityHoldoutEvidence:
    measurement_source_id: str
    protocol: str
    machine_fingerprint: str
    measurements: tuple[HeldoutCandidateMeasurement, ...]

    def validate(self) -> None:
        if not self.measurement_source_id.strip():
            raise ValueError("measurement_source_id cannot be empty")
        if not self.protocol.strip():
            raise ValueError("protocol cannot be empty")
        if not self.machine_fingerprint.strip():
            raise ValueError("machine_fingerprint cannot be empty")
        if not self.measurements:
            raise ValueError("at least one held-out candidate measurement is required")
        for item in self.measurements:
            item.validate()
            if item.measured <= 0:
                raise ValueError(
                    "measured held-out costs must be positive so relative search regret is defined"
                )


@dataclass(frozen=True)
class SearchQualityHoldoutValidationReport:
    measurement_source_id: str
    protocol: str
    machine_fingerprint: str
    workload_count: int
    candidate_count: int
    top_k: int
    oracle_hit_rate: float
    mean_top_k_recall: float
    mean_top1_regret_ratio: float
    worst_top1_regret_ratio: float
    minimum_required_workloads: int
    minimum_allowed_oracle_hit_rate: float
    minimum_allowed_mean_top_k_recall: float
    maximum_allowed_mean_top1_regret_ratio: float
    maximum_allowed_worst_top1_regret_ratio: float
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
            "oracle_hit_rate": self.oracle_hit_rate,
            "mean_top_k_recall": self.mean_top_k_recall,
            "mean_top1_regret_ratio": self.mean_top1_regret_ratio,
            "worst_top1_regret_ratio": self.worst_top1_regret_ratio,
            "minimum_required_workloads": self.minimum_required_workloads,
            "minimum_allowed_oracle_hit_rate": self.minimum_allowed_oracle_hit_rate,
            "minimum_allowed_mean_top_k_recall": self.minimum_allowed_mean_top_k_recall,
            "maximum_allowed_mean_top1_regret_ratio": self.maximum_allowed_mean_top1_regret_ratio,
            "maximum_allowed_worst_top1_regret_ratio": self.maximum_allowed_worst_top1_regret_ratio,
            "acceptance_passed": self.acceptance_passed,
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


def evaluate_search_quality_holdout(
    evidence: SearchQualityHoldoutEvidence,
    *,
    model_development_source_ids: Iterable[str],
    minimum_required_workloads: int = 2,
    top_k: int = 3,
    minimum_allowed_oracle_hit_rate: float,
    minimum_allowed_mean_top_k_recall: float,
    maximum_allowed_mean_top1_regret_ratio: float,
    maximum_allowed_worst_top1_regret_ratio: float,
    bootstrap_rounds: int = 2000,
    bootstrap_seed: int = 1337,
) -> SearchQualityHoldoutValidationReport:
    """Validate held-out search ranking quality against caller-declared limits.

    The underlying ranking/regret metrics come from ``evaluate_heldout_candidate_groups``.
    This function adds evidence-separation and acceptance-policy guards; it does not
    convert caller-supplied measurements into independent experimental evidence.
    """

    evidence.validate()
    if minimum_required_workloads < 2:
        raise ValueError("minimum_required_workloads must be at least 2")
    if top_k < 1:
        raise ValueError("top_k must be at least 1")
    _validate_rate("minimum_allowed_oracle_hit_rate", minimum_allowed_oracle_hit_rate)
    _validate_rate(
        "minimum_allowed_mean_top_k_recall", minimum_allowed_mean_top_k_recall
    )
    _validate_nonnegative(
        "maximum_allowed_mean_top1_regret_ratio",
        maximum_allowed_mean_top1_regret_ratio,
    )
    _validate_nonnegative(
        "maximum_allowed_worst_top1_regret_ratio",
        maximum_allowed_worst_top1_regret_ratio,
    )

    measurement_source_id = evidence.measurement_source_id.strip()
    protocol = evidence.protocol.strip()
    machine_fingerprint = evidence.machine_fingerprint.strip()
    development_sources = {
        source.strip() for source in model_development_source_ids if source.strip()
    }
    if measurement_source_id in development_sources:
        raise ValueError(
            "held-out measurement_source_id overlaps model development/calibration sources"
        )

    metrics: HeldoutEvaluationReport = evaluate_heldout_candidate_groups(
        evidence.measurements,
        top_k=top_k,
        bootstrap_rounds=bootstrap_rounds,
        bootstrap_seed=bootstrap_seed,
    )
    if metrics.workload_count < minimum_required_workloads:
        raise ValueError(
            f"held-out evidence must contain at least {minimum_required_workloads} distinct workloads"
        )

    regret_ratios = [item.top1_regret_ratio for item in metrics.workloads]
    if any(value is None for value in regret_ratios) or metrics.mean_top1_regret_ratio is None:
        raise ValueError("relative search regret must be defined for every held-out workload")
    concrete_regrets = [float(value) for value in regret_ratios if value is not None]
    worst_regret = max(concrete_regrets)

    accepted = (
        metrics.oracle_hit_rate >= minimum_allowed_oracle_hit_rate
        and metrics.mean_top_k_recall >= minimum_allowed_mean_top_k_recall
        and metrics.mean_top1_regret_ratio <= maximum_allowed_mean_top1_regret_ratio
        and worst_regret <= maximum_allowed_worst_top1_regret_ratio
    )

    return SearchQualityHoldoutValidationReport(
        measurement_source_id=measurement_source_id,
        protocol=protocol,
        machine_fingerprint=machine_fingerprint,
        workload_count=metrics.workload_count,
        candidate_count=metrics.candidate_count,
        top_k=top_k,
        oracle_hit_rate=metrics.oracle_hit_rate,
        mean_top_k_recall=metrics.mean_top_k_recall,
        mean_top1_regret_ratio=metrics.mean_top1_regret_ratio,
        worst_top1_regret_ratio=worst_regret,
        minimum_required_workloads=minimum_required_workloads,
        minimum_allowed_oracle_hit_rate=minimum_allowed_oracle_hit_rate,
        minimum_allowed_mean_top_k_recall=minimum_allowed_mean_top_k_recall,
        maximum_allowed_mean_top1_regret_ratio=maximum_allowed_mean_top1_regret_ratio,
        maximum_allowed_worst_top1_regret_ratio=maximum_allowed_worst_top1_regret_ratio,
        acceptance_passed=accepted,
    )
