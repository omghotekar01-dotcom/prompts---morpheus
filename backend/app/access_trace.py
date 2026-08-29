from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from .models import AccessDistribution


@dataclass(frozen=True)
class AccessTraceAnalysis:
    sample_count: int
    unique_keys: int
    unique_ratio: float
    top_1_percent_key_mass: float
    top_10_percent_key_mass: float
    sequential_adjacent_ratio: float
    normalized_frequency_entropy: float
    zipf_theta_estimate: float | None
    zipf_log_rank_r2: float | None
    suggested_distribution: AccessDistribution
    suggestion_reason: str
    evidence_state: str = "TRACE_DESCRIPTIVE_METRICS_HEURISTIC_CLASSIFICATION_NOT_CONTROL_EVIDENCE"

    def as_dict(self) -> dict[str, object]:
        return {
            "sample_count": self.sample_count,
            "unique_keys": self.unique_keys,
            "unique_ratio": self.unique_ratio,
            "top_1_percent_key_mass": self.top_1_percent_key_mass,
            "top_10_percent_key_mass": self.top_10_percent_key_mass,
            "sequential_adjacent_ratio": self.sequential_adjacent_ratio,
            "normalized_frequency_entropy": self.normalized_frequency_entropy,
            "zipf_theta_estimate": self.zipf_theta_estimate,
            "zipf_log_rank_r2": self.zipf_log_rank_r2,
            "suggested_distribution": self.suggested_distribution.value,
            "suggestion_reason": self.suggestion_reason,
            "evidence_state": self.evidence_state,
            "eligible_for_runtime_automatic_control": False,
            "truth_boundary": (
                "The numeric metrics are computed directly from the supplied finite key window. The distribution label is a deterministic development heuristic, "
                "not a goodness-of-fit test, causal explanation, stationary-workload guarantee, or validated trigger for automatic runtime adaptation."
            ),
        }


def _top_key_mass(counts: Counter[int], fraction: float, sample_count: int) -> float:
    take = max(1, math.ceil(len(counts) * fraction))
    top = sum(value for _key, value in counts.most_common(take))
    return top / sample_count


def _normalized_entropy(counts: Counter[int], sample_count: int) -> float:
    if len(counts) <= 1:
        return 0.0
    entropy = 0.0
    for count in counts.values():
        probability = count / sample_count
        entropy -= probability * math.log(probability)
    return entropy / math.log(len(counts))


def _zipf_rank_fit(counts: Counter[int]) -> tuple[float | None, float | None]:
    frequencies = sorted(counts.values(), reverse=True)
    if len(frequencies) < 4 or len(set(frequencies)) < 2:
        return None, None

    xs = [math.log(rank) for rank in range(1, len(frequencies) + 1)]
    ys = [math.log(float(frequency)) for frequency in frequencies]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    ss_x = sum((value - mean_x) ** 2 for value in xs)
    if ss_x == 0:
        return None, None
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = covariance / ss_x
    intercept = mean_y - slope * mean_x
    ss_total = sum((y - mean_y) ** 2 for y in ys)
    if ss_total == 0:
        return max(0.0, -slope), None
    ss_residual = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    r2 = max(0.0, min(1.0, 1.0 - ss_residual / ss_total))
    return max(0.0, -slope), r2


def analyze_access_trace(keys: Iterable[int]) -> AccessTraceAnalysis:
    """Characterize one finite integer-key access window without claiming stationarity.

    Thresholds used for the suggested label are intentionally visible and
    conservative development heuristics. Research-grade distribution inference
    must compare explicit statistical models on held-out traces before any
    suggestion is promoted into the runtime controller.
    """

    values = [int(value) for value in keys]
    if len(values) < 2:
        raise ValueError("access trace requires at least two keys")
    if len(values) > 1_000_000:
        raise ValueError("access trace exceeds the 1,000,000-sample safety limit")

    counts = Counter(values)
    sample_count = len(values)
    sequential_hits = sum(
        1 for left, right in zip(values, values[1:]) if right == left + 1
    )
    sequential_ratio = sequential_hits / (sample_count - 1)
    top_1 = _top_key_mass(counts, 0.01, sample_count)
    top_10 = _top_key_mass(counts, 0.10, sample_count)
    entropy = _normalized_entropy(counts, sample_count)
    theta, r2 = _zipf_rank_fit(counts)

    if sequential_ratio >= 0.80:
        suggested = AccessDistribution.SEQUENTIAL
        reason = "at least 80% of adjacent accesses advance by exactly one key"
    elif top_10 >= 0.70:
        suggested = AccessDistribution.HOTSPOT
        reason = "the hottest 10% of observed unique keys account for at least 70% of accesses"
    elif theta is not None and r2 is not None and 0.5 <= theta <= 2.5 and r2 >= 0.85:
        suggested = AccessDistribution.ZIPF
        reason = "rank-frequency log fit passes the development Zipf-shape heuristic (theta 0.5-2.5, R^2 >= 0.85)"
    else:
        suggested = AccessDistribution.UNIFORM
        reason = "the finite window does not cross the sequential, hotspot, or Zipf-shape development heuristics"

    return AccessTraceAnalysis(
        sample_count=sample_count,
        unique_keys=len(counts),
        unique_ratio=round(len(counts) / sample_count, 8),
        top_1_percent_key_mass=round(top_1, 8),
        top_10_percent_key_mass=round(top_10, 8),
        sequential_adjacent_ratio=round(sequential_ratio, 8),
        normalized_frequency_entropy=round(entropy, 8),
        zipf_theta_estimate=round(theta, 8) if theta is not None else None,
        zipf_log_rank_r2=round(r2, 8) if r2 is not None else None,
        suggested_distribution=suggested,
        suggestion_reason=reason,
    )
