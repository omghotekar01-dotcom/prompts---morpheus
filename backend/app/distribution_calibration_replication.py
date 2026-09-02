from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from app.distribution_calibration_holdout import DistributionCalibrationHoldoutReport


EVIDENCE_STATE = "METHODOLOGY_ONLY_CALLER_SUPPLIED_CROSS_MACHINE_REPLICATION"
TRUTH_BOUNDARY = (
    "This gate aggregates caller-supplied held-out calibration reports across distinct machine fingerprints "
    "under one measurement protocol and evaluates only caller-declared replication limits. It does not prove "
    "independent laboratories, measurement validity, publication-grade replication, performance superiority, "
    "novelty, or production authorization."
)


@dataclass(frozen=True)
class DistributionCalibrationReplicationReport:
    machine_count: int
    protocol: str
    mean_machine_mape: float
    max_machine_mape: float
    min_machine_mape: float
    machine_mape_spread: float
    worst_machine_ape: float
    max_allowed_machine_mape_spread: float
    all_holdouts_accepted: bool
    replication_passed: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "machine_count": self.machine_count,
            "protocol": self.protocol,
            "mean_machine_mape": self.mean_machine_mape,
            "max_machine_mape": self.max_machine_mape,
            "min_machine_mape": self.min_machine_mape,
            "machine_mape_spread": self.machine_mape_spread,
            "worst_machine_ape": self.worst_machine_ape,
            "max_allowed_machine_mape_spread": self.max_allowed_machine_mape_spread,
            "all_holdouts_accepted": self.all_holdouts_accepted,
            "replication_passed": self.replication_passed,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def evaluate_distribution_calibration_replication(
    reports: Iterable[DistributionCalibrationHoldoutReport],
    *,
    max_allowed_machine_mape_spread: float,
    minimum_distinct_machines: int = 2,
) -> DistributionCalibrationReplicationReport:
    """Evaluate cross-machine replication of already-evaluated held-out calibration reports.

    This gate intentionally compares calibration *error*, not raw latency, because machine-dependent latency
    magnitudes are not directly comparable. It refuses mixed measurement protocols so a replication result cannot
    silently pool incompatible experimental procedures, and every constituent holdout must already have satisfied
    its own caller-declared acceptance limits.

    The caller supplies the allowed cross-machine MAPE spread. Passing means only that the supplied reports meet
    that declared replication criterion; it is not an assertion that the campaigns were independently conducted.
    """

    items = list(reports)
    if not items:
        raise ValueError("at least one held-out calibration report is required")
    if minimum_distinct_machines < 2:
        raise ValueError("minimum_distinct_machines must be at least 2")
    if not math.isfinite(max_allowed_machine_mape_spread) or max_allowed_machine_mape_spread < 0:
        raise ValueError("max_allowed_machine_mape_spread must be finite and non-negative")

    protocols = {report.protocol for report in items}
    if len(protocols) != 1:
        raise ValueError("replication reports must share one measurement protocol")

    machines = [report.machine_fingerprint for report in items]
    if len(machines) != len(set(machines)):
        raise ValueError("replication requires at most one held-out report per machine fingerprint")
    if len(set(machines)) < minimum_distinct_machines:
        raise ValueError(
            f"replication requires at least {minimum_distinct_machines} distinct machine fingerprints"
        )

    for report in items:
        if report.automatic_control_allowed:
            raise ValueError("held-out evidence cannot authorize automatic control")
        if not report.acceptance_passed:
            raise ValueError("every constituent held-out report must satisfy its declared acceptance limits")
        for field_name in (
            "mean_absolute_percentage_error",
            "max_absolute_percentage_error",
        ):
            value = getattr(report, field_name)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{field_name} must be finite and non-negative")

    mapes = [report.mean_absolute_percentage_error for report in items]
    spread = max(mapes) - min(mapes)

    return DistributionCalibrationReplicationReport(
        machine_count=len(set(machines)),
        protocol=next(iter(protocols)),
        mean_machine_mape=sum(mapes) / len(mapes),
        max_machine_mape=max(mapes),
        min_machine_mape=min(mapes),
        machine_mape_spread=spread,
        worst_machine_ape=max(report.max_absolute_percentage_error for report in items),
        max_allowed_machine_mape_spread=max_allowed_machine_mape_spread,
        all_holdouts_accepted=True,
        replication_passed=spread <= max_allowed_machine_mape_spread,
    )
