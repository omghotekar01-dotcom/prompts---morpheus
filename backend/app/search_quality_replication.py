from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from .search_quality_holdout import (
    EVIDENCE_STATE as HOLDOUT_EVIDENCE_STATE,
    SearchQualityHoldoutValidationReport,
)


EVIDENCE_STATE = "METHODOLOGY_ONLY_CALLER_SUPPLIED_SEARCH_QUALITY_REPLICATION"
TRUTH_BOUNDARY = (
    "This gate checks whether caller-supplied, already-accepted held-out search-quality reports from distinct "
    "declared measurement sources and machine fingerprints remain consistent under one protocol and one "
    "acceptance policy, using only caller-declared cross-report spread limits. Distinct source identifiers and "
    "machine fingerprints are structural separation guards; they do not prove independent collection, independent "
    "laboratories, instrumentation validity, publication-grade replication, search/performance superiority, novelty, "
    "or production authorization."
)


@dataclass(frozen=True)
class SearchQualityReplicationReport:
    source_count: int
    machine_count: int
    protocol: str
    mean_oracle_hit_rate: float
    oracle_hit_rate_spread: float
    mean_machine_top1_regret_ratio: float
    mean_top1_regret_ratio_spread: float
    max_machine_worst_top1_regret_ratio: float
    worst_top1_regret_ratio_spread: float
    max_allowed_oracle_hit_rate_spread: float
    max_allowed_mean_top1_regret_ratio_spread: float
    max_allowed_worst_top1_regret_ratio_spread: float
    all_holdouts_accepted: bool
    replication_passed: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "source_count": self.source_count,
            "machine_count": self.machine_count,
            "protocol": self.protocol,
            "mean_oracle_hit_rate": self.mean_oracle_hit_rate,
            "oracle_hit_rate_spread": self.oracle_hit_rate_spread,
            "mean_machine_top1_regret_ratio": self.mean_machine_top1_regret_ratio,
            "mean_top1_regret_ratio_spread": self.mean_top1_regret_ratio_spread,
            "max_machine_worst_top1_regret_ratio": self.max_machine_worst_top1_regret_ratio,
            "worst_top1_regret_ratio_spread": self.worst_top1_regret_ratio_spread,
            "max_allowed_oracle_hit_rate_spread": self.max_allowed_oracle_hit_rate_spread,
            "max_allowed_mean_top1_regret_ratio_spread": self.max_allowed_mean_top1_regret_ratio_spread,
            "max_allowed_worst_top1_regret_ratio_spread": self.max_allowed_worst_top1_regret_ratio_spread,
            "all_holdouts_accepted": self.all_holdouts_accepted,
            "replication_passed": self.replication_passed,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def _validate_nonnegative(name: str, value: float) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and non-negative")


def _normalized_identity(value: str, *, name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} cannot be empty")
    return normalized


def _acceptance_policy(report: SearchQualityHoldoutValidationReport) -> tuple[object, ...]:
    return (
        report.minimum_required_workloads,
        report.minimum_allowed_oracle_hit_rate,
        report.minimum_allowed_mean_top_k_recall,
        report.maximum_allowed_mean_top1_regret_ratio,
        report.maximum_allowed_worst_top1_regret_ratio,
    )


def evaluate_search_quality_replication(
    reports: Iterable[SearchQualityHoldoutValidationReport],
    *,
    max_allowed_oracle_hit_rate_spread: float,
    max_allowed_mean_top1_regret_ratio_spread: float,
    max_allowed_worst_top1_regret_ratio_spread: float,
    minimum_distinct_sources: int = 2,
    minimum_distinct_machines: int = 2,
) -> SearchQualityReplicationReport:
    """Evaluate cross-source/cross-machine consistency of accepted P24 holdout reports.

    Only top-1 decision metrics are pooled here. ``mean_top_k_recall`` is intentionally not aggregated because the
    current P24 report does not bind the ``top_k`` value into its serialized report; silently pooling recall values
    from potentially different k values would create a false comparability claim. Constituent reports must still
    share the same declared P24 acceptance policy and must each have passed it.

    Passing this gate means only that supplied reports satisfy the caller's declared spread limits. It does not
    establish that the named sources or machines represent genuinely independent experiments.
    """

    items = list(reports)
    if not items:
        raise ValueError("at least one held-out search-quality report is required")
    if minimum_distinct_sources < 2:
        raise ValueError("minimum_distinct_sources must be at least 2")
    if minimum_distinct_machines < 2:
        raise ValueError("minimum_distinct_machines must be at least 2")

    _validate_nonnegative("max_allowed_oracle_hit_rate_spread", max_allowed_oracle_hit_rate_spread)
    _validate_nonnegative(
        "max_allowed_mean_top1_regret_ratio_spread",
        max_allowed_mean_top1_regret_ratio_spread,
    )
    _validate_nonnegative(
        "max_allowed_worst_top1_regret_ratio_spread",
        max_allowed_worst_top1_regret_ratio_spread,
    )

    protocols = {
        _normalized_identity(report.protocol, name="protocol") for report in items
    }
    if len(protocols) != 1:
        raise ValueError("replication reports must share one measurement protocol")

    sources = [
        _normalized_identity(report.measurement_source_id, name="measurement_source_id")
        for report in items
    ]
    if len(sources) != len(set(sources)):
        raise ValueError("replication requires at most one report per normalized measurement source")
    if len(set(sources)) < minimum_distinct_sources:
        raise ValueError(
            f"replication requires at least {minimum_distinct_sources} distinct measurement sources"
        )

    machines = [
        _normalized_identity(report.machine_fingerprint, name="machine_fingerprint")
        for report in items
    ]
    if len(machines) != len(set(machines)):
        raise ValueError("replication requires at most one report per normalized machine fingerprint")
    if len(set(machines)) < minimum_distinct_machines:
        raise ValueError(
            f"replication requires at least {minimum_distinct_machines} distinct machine fingerprints"
        )

    policies = {_acceptance_policy(report) for report in items}
    if len(policies) != 1:
        raise ValueError("replication reports must share one declared holdout acceptance policy")

    for report in items:
        if report.evidence_state != HOLDOUT_EVIDENCE_STATE:
            raise ValueError("replication accepts only P24 held-out search-quality methodology reports")
        if report.automatic_control_allowed:
            raise ValueError("held-out search-quality evidence cannot authorize automatic control")
        if not report.acceptance_passed:
            raise ValueError("every constituent held-out report must satisfy its declared acceptance limits")
        if report.workload_count < report.minimum_required_workloads:
            raise ValueError("constituent workload coverage is inconsistent with its declared minimum")
        if report.candidate_count < report.workload_count:
            raise ValueError("constituent candidate_count cannot be smaller than workload_count")

        if not math.isfinite(report.oracle_hit_rate) or not 0.0 <= report.oracle_hit_rate <= 1.0:
            raise ValueError("oracle_hit_rate must be finite and between 0 and 1")
        _validate_nonnegative("mean_top1_regret_ratio", report.mean_top1_regret_ratio)
        _validate_nonnegative("worst_top1_regret_ratio", report.worst_top1_regret_ratio)
        if report.worst_top1_regret_ratio < report.mean_top1_regret_ratio:
            raise ValueError("worst_top1_regret_ratio cannot be smaller than mean_top1_regret_ratio")

    oracle_hits = [report.oracle_hit_rate for report in items]
    mean_regrets = [report.mean_top1_regret_ratio for report in items]
    worst_regrets = [report.worst_top1_regret_ratio for report in items]

    oracle_spread = max(oracle_hits) - min(oracle_hits)
    mean_regret_spread = max(mean_regrets) - min(mean_regrets)
    worst_regret_spread = max(worst_regrets) - min(worst_regrets)
    passed = (
        oracle_spread <= max_allowed_oracle_hit_rate_spread
        and mean_regret_spread <= max_allowed_mean_top1_regret_ratio_spread
        and worst_regret_spread <= max_allowed_worst_top1_regret_ratio_spread
    )

    return SearchQualityReplicationReport(
        source_count=len(set(sources)),
        machine_count=len(set(machines)),
        protocol=next(iter(protocols)),
        mean_oracle_hit_rate=sum(oracle_hits) / len(oracle_hits),
        oracle_hit_rate_spread=oracle_spread,
        mean_machine_top1_regret_ratio=sum(mean_regrets) / len(mean_regrets),
        mean_top1_regret_ratio_spread=mean_regret_spread,
        max_machine_worst_top1_regret_ratio=max(worst_regrets),
        worst_top1_regret_ratio_spread=worst_regret_spread,
        max_allowed_oracle_hit_rate_spread=max_allowed_oracle_hit_rate_spread,
        max_allowed_mean_top1_regret_ratio_spread=max_allowed_mean_top1_regret_ratio_spread,
        max_allowed_worst_top1_regret_ratio_spread=max_allowed_worst_top1_regret_ratio_spread,
        all_holdouts_accepted=True,
        replication_passed=passed,
    )
