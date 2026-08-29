from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .access_trace import analyze_access_trace
from .access_trace_drift import compare_access_trace_windows


@dataclass(frozen=True)
class TraceWindowSummary:
    window_index: int
    start: int
    end: int
    sample_count: int
    suggested_distribution: str
    top_10_percent_key_mass: float
    sequential_adjacent_ratio: float
    normalized_frequency_entropy: float

    def as_dict(self) -> dict[str, object]:
        return {
            "window_index": self.window_index,
            "start": self.start,
            "end": self.end,
            "sample_count": self.sample_count,
            "suggested_distribution": self.suggested_distribution,
            "top_10_percent_key_mass": self.top_10_percent_key_mass,
            "sequential_adjacent_ratio": self.sequential_adjacent_ratio,
            "normalized_frequency_entropy": self.normalized_frequency_entropy,
        }


@dataclass(frozen=True)
class TracePhaseBoundary:
    previous_window_index: int
    current_window_index: int
    boundary_sample_index: int
    key_frequency_tv_distance: float
    normalized_jensen_shannon_divergence: float
    top_10_percent_key_jaccard: float

    def as_dict(self) -> dict[str, object]:
        return {
            "previous_window_index": self.previous_window_index,
            "current_window_index": self.current_window_index,
            "boundary_sample_index": self.boundary_sample_index,
            "key_frequency_tv_distance": self.key_frequency_tv_distance,
            "normalized_jensen_shannon_divergence": self.normalized_jensen_shannon_divergence,
            "top_10_percent_key_jaccard": self.top_10_percent_key_jaccard,
        }


@dataclass(frozen=True)
class AccessTracePhaseReport:
    sample_count: int
    window_size: int
    step_size: int
    drift_threshold: float
    windows: tuple[TraceWindowSummary, ...]
    boundaries: tuple[TracePhaseBoundary, ...]
    evidence_state: str = "ROLLING_FINITE_TRACE_PHASE_CANDIDATES_NOT_AUTOMATIC_CONTROL_EVIDENCE"

    def as_dict(self) -> dict[str, object]:
        return {
            "sample_count": self.sample_count,
            "window_size": self.window_size,
            "step_size": self.step_size,
            "drift_threshold": self.drift_threshold,
            "window_count": len(self.windows),
            "boundary_count": len(self.boundaries),
            "windows": [item.as_dict() for item in self.windows],
            "boundaries": [item.as_dict() for item in self.boundaries],
            "evidence_state": self.evidence_state,
            "eligible_for_runtime_automatic_control": False,
            "truth_boundary": (
                "Boundaries are threshold crossings between adjacent finite empirical windows. Overlap, window size, trace length and threshold materially affect the result; "
                "this report is exploratory change-point evidence, not a statistically calibrated online detector or automatic adaptation authorization."
            ),
        }


def analyze_trace_phases(
    keys: Iterable[int],
    *,
    window_size: int = 500,
    step_size: int | None = None,
    drift_threshold: float = 0.20,
) -> AccessTracePhaseReport:
    values = [int(value) for value in keys]
    if len(values) < 4:
        raise ValueError("phase analysis requires at least four access samples")
    if len(values) > 1_000_000:
        raise ValueError("phase analysis exceeds the 1,000,000-sample safety limit")
    if window_size < 2:
        raise ValueError("window_size must be at least two")
    if window_size > len(values):
        raise ValueError("window_size cannot exceed trace length")
    resolved_step = window_size if step_size is None else step_size
    if resolved_step < 1:
        raise ValueError("step_size must be positive")
    if not 0 <= drift_threshold <= 1:
        raise ValueError("drift_threshold must be between 0 and 1")

    slices: list[tuple[int, int, list[int]]] = []
    start = 0
    while start + window_size <= len(values):
        end = start + window_size
        slices.append((start, end, values[start:end]))
        start += resolved_step
    if len(slices) < 2:
        raise ValueError("phase analysis requires at least two complete windows")

    summaries: list[TraceWindowSummary] = []
    for index, (start, end, window) in enumerate(slices):
        analysis = analyze_access_trace(window)
        summaries.append(
            TraceWindowSummary(
                window_index=index,
                start=start,
                end=end,
                sample_count=len(window),
                suggested_distribution=analysis.suggested_distribution.value,
                top_10_percent_key_mass=analysis.top_10_percent_key_mass,
                sequential_adjacent_ratio=analysis.sequential_adjacent_ratio,
                normalized_frequency_entropy=analysis.normalized_frequency_entropy,
            )
        )

    boundaries: list[TracePhaseBoundary] = []
    for index in range(1, len(slices)):
        previous = slices[index - 1][2]
        current_start, _current_end, current = slices[index]
        drift = compare_access_trace_windows(previous, current, threshold=drift_threshold)
        if drift.drifted:
            boundaries.append(
                TracePhaseBoundary(
                    previous_window_index=index - 1,
                    current_window_index=index,
                    boundary_sample_index=current_start,
                    key_frequency_tv_distance=drift.key_frequency_tv_distance,
                    normalized_jensen_shannon_divergence=drift.normalized_jensen_shannon_divergence,
                    top_10_percent_key_jaccard=drift.top_10_percent_key_jaccard,
                )
            )

    return AccessTracePhaseReport(
        sample_count=len(values),
        window_size=window_size,
        step_size=resolved_step,
        drift_threshold=drift_threshold,
        windows=tuple(summaries),
        boundaries=tuple(boundaries),
    )
