from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Iterable


EVIDENCE_STATE = "METHODOLOGY_ONLY_CALLER_SUPPLIED_HELDOUT_DISTRIBUTION_MEASUREMENTS"
TRUTH_BOUNDARY = (
    "This gate validates caller-supplied, distribution-bound holdout records and reports error against "
    "caller-declared acceptance limits. It does not prove measurement independence, publication-grade "
    "benchmark quality, performance superiority, novelty, or production authorization."
)


@dataclass(frozen=True)
class DistributionCalibrationHoldoutPoint:
    holdout_id: str
    measurement_source_id: str
    primitive: str
    implementation_id: str
    operation: str
    distribution_signature: str
    protocol: str
    machine_fingerprint: str
    predicted_ns_per_op: float
    measured_ns_per_op: float

    def validate(self) -> None:
        for field_name in (
            "holdout_id",
            "measurement_source_id",
            "primitive",
            "implementation_id",
            "operation",
            "distribution_signature",
            "protocol",
            "machine_fingerprint",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} cannot be empty")
        if self.distribution_signature == "uniform":
            raise ValueError("distribution calibration holdout must be nonuniform")
        for field_name in ("predicted_ns_per_op", "measured_ns_per_op"):
            value = getattr(self, field_name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{field_name} must be finite and positive")


@dataclass(frozen=True)
class DistributionCalibrationHoldoutReport:
    point_count: int
    distribution_count: int
    mean_absolute_percentage_error: float
    median_absolute_percentage_error: float
    max_absolute_percentage_error: float
    mean_absolute_error_ns: float
    max_allowed_mean_ape: float
    max_allowed_worst_ape: float
    acceptance_passed: bool
    protocol: str
    machine_fingerprint: str
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "point_count": self.point_count,
            "distribution_count": self.distribution_count,
            "mean_absolute_percentage_error": self.mean_absolute_percentage_error,
            "median_absolute_percentage_error": self.median_absolute_percentage_error,
            "max_absolute_percentage_error": self.max_absolute_percentage_error,
            "mean_absolute_error_ns": self.mean_absolute_error_ns,
            "max_allowed_mean_ape": self.max_allowed_mean_ape,
            "max_allowed_worst_ape": self.max_allowed_worst_ape,
            "acceptance_passed": self.acceptance_passed,
            "protocol": self.protocol,
            "machine_fingerprint": self.machine_fingerprint,
            "evidence_state": self.evidence_state,
            "automatic_control_allowed": self.automatic_control_allowed,
            "truth_boundary": TRUTH_BOUNDARY,
        }


def evaluate_distribution_calibration_holdout(
    points: Iterable[DistributionCalibrationHoldoutPoint],
    *,
    calibration_source_ids: Iterable[str],
    max_allowed_mean_ape: float,
    max_allowed_worst_ape: float,
    minimum_distinct_distributions: int = 2,
) -> DistributionCalibrationHoldoutReport:
    """Validate a nonuniform calibration holdout without promoting it to runtime truth.

    The caller must disclose the source identities used to construct/calibrate the predictions. A holdout
    measurement may not reuse one of those source identities. All holdout records are also required to share
    one protocol and machine fingerprint so error is not silently pooled across incompatible campaigns.

    Acceptance limits are supplied by the experiment protocol/caller rather than invented by this function.
    A passing report is therefore evidence that the supplied records satisfy those declared limits only.
    """

    items = list(points)
    if not items:
        raise ValueError("at least one distribution calibration holdout point is required")
    if minimum_distinct_distributions < 2:
        raise ValueError("minimum_distinct_distributions must be at least 2")
    for name, value in (
        ("max_allowed_mean_ape", max_allowed_mean_ape),
        ("max_allowed_worst_ape", max_allowed_worst_ape),
    ):
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be finite and non-negative")

    training_sources = list(calibration_source_ids)
    if not training_sources:
        raise ValueError("at least one calibration source identity is required")
    if any(not isinstance(source, str) or not source.strip() for source in training_sources):
        raise ValueError("calibration source identities cannot be empty")
    if len(training_sources) != len(set(training_sources)):
        raise ValueError("duplicate calibration source identity")
    training_source_set = set(training_sources)

    for item in items:
        item.validate()
    holdout_ids = [item.holdout_id for item in items]
    if len(holdout_ids) != len(set(holdout_ids)):
        raise ValueError("duplicate holdout_id")
    holdout_sources = [item.measurement_source_id for item in items]
    if len(holdout_sources) != len(set(holdout_sources)):
        raise ValueError("duplicate holdout measurement_source_id")
    leaked = sorted(set(holdout_sources) & training_source_set)
    if leaked:
        raise ValueError(f"calibration/holdout source leakage detected: {', '.join(leaked)}")

    protocols = {item.protocol for item in items}
    if len(protocols) != 1:
        raise ValueError("holdout points must share one measurement protocol")
    machines = {item.machine_fingerprint for item in items}
    if len(machines) != 1:
        raise ValueError("holdout points must share one machine fingerprint")
    distributions = {item.distribution_signature for item in items}
    if len(distributions) < minimum_distinct_distributions:
        raise ValueError(
            f"holdout requires at least {minimum_distinct_distributions} distinct nonuniform distributions"
        )

    absolute_errors = [abs(item.predicted_ns_per_op - item.measured_ns_per_op) for item in items]
    apes = [error / item.measured_ns_per_op for error, item in zip(absolute_errors, items)]
    mean_ape = sum(apes) / len(apes)
    worst_ape = max(apes)
    return DistributionCalibrationHoldoutReport(
        point_count=len(items),
        distribution_count=len(distributions),
        mean_absolute_percentage_error=mean_ape,
        median_absolute_percentage_error=statistics.median(apes),
        max_absolute_percentage_error=worst_ape,
        mean_absolute_error_ns=sum(absolute_errors) / len(absolute_errors),
        max_allowed_mean_ape=max_allowed_mean_ape,
        max_allowed_worst_ape=max_allowed_worst_ape,
        acceptance_passed=(
            mean_ape <= max_allowed_mean_ape and worst_ape <= max_allowed_worst_ape
        ),
        protocol=next(iter(protocols)),
        machine_fingerprint=next(iter(machines)),
    )
