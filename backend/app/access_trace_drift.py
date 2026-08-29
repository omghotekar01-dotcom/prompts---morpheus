from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class AccessTraceDriftReport:
    baseline_samples: int
    observed_samples: int
    baseline_unique_keys: int
    observed_unique_keys: int
    key_frequency_tv_distance: float
    normalized_jensen_shannon_divergence: float
    top_10_percent_key_jaccard: float
    threshold: float
    drifted: bool
    evidence_state: str = "FINITE_TRACE_WINDOWS_EMPIRICAL_FREQUENCY_DRIFT_NOT_AUTOMATIC_CONTROL_EVIDENCE"

    def as_dict(self) -> dict[str, object]:
        return {
            "baseline_samples": self.baseline_samples,
            "observed_samples": self.observed_samples,
            "baseline_unique_keys": self.baseline_unique_keys,
            "observed_unique_keys": self.observed_unique_keys,
            "key_frequency_tv_distance": self.key_frequency_tv_distance,
            "normalized_jensen_shannon_divergence": self.normalized_jensen_shannon_divergence,
            "top_10_percent_key_jaccard": self.top_10_percent_key_jaccard,
            "threshold": self.threshold,
            "drifted": self.drifted,
            "evidence_state": self.evidence_state,
            "eligible_for_runtime_automatic_control": False,
            "truth_boundary": (
                "Distances compare only the two supplied finite empirical key-frequency windows. They do not establish stationarity, root cause, future persistence, "
                "or a validated automatic adaptation threshold."
            ),
        }


def _window(values: Iterable[int], name: str) -> list[int]:
    items = [int(value) for value in values]
    if len(items) < 2:
        raise ValueError(f"{name} access window requires at least two keys")
    if len(items) > 1_000_000:
        raise ValueError(f"{name} access window exceeds the 1,000,000-sample safety limit")
    return items


def _probabilities(values: list[int]) -> tuple[Counter[int], dict[int, float]]:
    counts = Counter(values)
    total = len(values)
    return counts, {key: count / total for key, count in counts.items()}


def _tv(a: dict[int, float], b: dict[int, float]) -> float:
    keys = set(a) | set(b)
    return 0.5 * sum(abs(a.get(key, 0.0) - b.get(key, 0.0)) for key in keys)


def _kl_to_mixture(source: dict[int, float], mixture: dict[int, float]) -> float:
    total = 0.0
    for key, probability in source.items():
        if probability > 0:
            total += probability * math.log(probability / mixture[key])
    return total


def _normalized_js(a: dict[int, float], b: dict[int, float]) -> float:
    keys = set(a) | set(b)
    mixture = {key: 0.5 * (a.get(key, 0.0) + b.get(key, 0.0)) for key in keys}
    js = 0.5 * _kl_to_mixture(a, mixture) + 0.5 * _kl_to_mixture(b, mixture)
    return js / math.log(2.0)


def _top_keys(counts: Counter[int], fraction: float = 0.10) -> set[int]:
    take = max(1, math.ceil(len(counts) * fraction))
    return {key for key, _count in counts.most_common(take)}


def compare_access_trace_windows(
    baseline_keys: Iterable[int],
    observed_keys: Iterable[int],
    *,
    threshold: float = 0.20,
) -> AccessTraceDriftReport:
    """Compare finite empirical key-frequency windows with bounded distances."""

    if not 0 <= threshold <= 1:
        raise ValueError("trace drift threshold must be between 0 and 1")
    baseline = _window(baseline_keys, "baseline")
    observed = _window(observed_keys, "observed")
    baseline_counts, baseline_prob = _probabilities(baseline)
    observed_counts, observed_prob = _probabilities(observed)

    tv = _tv(baseline_prob, observed_prob)
    js = _normalized_js(baseline_prob, observed_prob)
    baseline_top = _top_keys(baseline_counts)
    observed_top = _top_keys(observed_counts)
    union = baseline_top | observed_top
    top_jaccard = len(baseline_top & observed_top) / len(union) if union else 1.0

    return AccessTraceDriftReport(
        baseline_samples=len(baseline),
        observed_samples=len(observed),
        baseline_unique_keys=len(baseline_counts),
        observed_unique_keys=len(observed_counts),
        key_frequency_tv_distance=round(tv, 8),
        normalized_jensen_shannon_divergence=round(max(0.0, min(1.0, js)), 8),
        top_10_percent_key_jaccard=round(top_jaccard, 8),
        threshold=round(threshold, 8),
        drifted=tv >= threshold,
    )
