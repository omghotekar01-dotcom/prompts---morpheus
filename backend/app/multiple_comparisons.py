from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class HolmHypothesis:
    label: str
    raw_p: float
    adjusted_p: float
    rejected: bool
    rank: int
    threshold: float

    def as_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "raw_p": self.raw_p,
            "adjusted_p": self.adjusted_p,
            "rejected": self.rejected,
            "rank": self.rank,
            "threshold": self.threshold,
        }


@dataclass(frozen=True)
class HolmCorrection:
    alpha: float
    family_size: int
    hypotheses: tuple[HolmHypothesis, ...]
    method: str = "HOLM_BONFERRONI_STEP_DOWN"
    evidence_state: str = "CORRECTED_CALLER_SUPPLIED_P_VALUES"

    def as_dict(self) -> dict[str, object]:
        return {
            "alpha": self.alpha,
            "family_size": self.family_size,
            "method": self.method,
            "hypotheses": [item.as_dict() for item in self.hypotheses],
            "evidence_state": self.evidence_state,
            "truth_note": (
                "The correction controls family-wise error for the supplied p-values; "
                "it does not validate the underlying experiment design or independence assumptions."
            ),
        }


def holm_bonferroni(p_values: Mapping[str, float], *, alpha: float = 0.05) -> HolmCorrection:
    """Apply deterministic Holm-Bonferroni family-wise error correction.

    Labels are used as deterministic tie breakers so the serialized result is
    stable across mapping insertion orders. Adjusted p-values use the standard
    monotone step-down construction: max of all preceding `(m-rank+1)*p` terms,
    capped at one. Rejection stops at the first hypothesis that exceeds its
    sequential Holm threshold.
    """

    if not math.isfinite(alpha) or not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be finite and strictly between 0 and 1")
    if not p_values:
        raise ValueError("at least one p-value is required")

    normalized: list[tuple[str, float]] = []
    for raw_label, raw_p in p_values.items():
        label = str(raw_label).strip()
        if not label:
            raise ValueError("hypothesis labels cannot be empty")
        value = float(raw_p)
        if not math.isfinite(value) or value < 0.0 or value > 1.0:
            raise ValueError(f"p-value for {label!r} must be finite and in [0, 1]")
        normalized.append((label, value))

    normalized.sort(key=lambda item: (item[1], item[0]))
    family_size = len(normalized)
    running_adjusted = 0.0
    still_rejecting = True
    hypotheses: list[HolmHypothesis] = []

    for offset, (label, raw_p) in enumerate(normalized):
        rank = offset + 1
        remaining = family_size - offset
        threshold = alpha / remaining
        running_adjusted = max(running_adjusted, min(1.0, raw_p * remaining))
        rejected = bool(still_rejecting and raw_p <= threshold)
        if not rejected:
            still_rejecting = False
        hypotheses.append(
            HolmHypothesis(
                label=label,
                raw_p=raw_p,
                adjusted_p=running_adjusted,
                rejected=rejected,
                rank=rank,
                threshold=threshold,
            )
        )

    return HolmCorrection(alpha=alpha, family_size=family_size, hypotheses=tuple(hypotheses))
