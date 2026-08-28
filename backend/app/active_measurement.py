from __future__ import annotations

from dataclasses import dataclass

from .models import CandidateResult, SynthesisResult


@dataclass(frozen=True)
class CandidateScoreInterval:
    candidate_id: str
    score: float
    uncertainty_ratio: float
    lower: float
    upper: float
    prediction_source: str

    def as_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "score": self.score,
            "uncertainty_ratio": self.uncertainty_ratio,
            "lower": self.lower,
            "upper": self.upper,
            "prediction_source": self.prediction_source,
        }


@dataclass(frozen=True)
class MeasurementTarget:
    primitive: str
    operation: str
    candidate_ids: tuple[str, ...]
    priority: float
    reason: str

    def as_dict(self) -> dict[str, object]:
        return {
            "primitive": self.primitive,
            "operation": self.operation,
            "candidate_ids": list(self.candidate_ids),
            "priority": self.priority,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class DecisionConfidenceAssessment:
    winner_id: str | None
    decision_confident_under_interval_heuristic: bool
    ambiguous_candidate_ids: tuple[str, ...]
    runner_up_score_gap: float | None
    winner_interval: CandidateScoreInterval | None
    ambiguous_intervals: tuple[CandidateScoreInterval, ...]
    recommended_measurements: tuple[MeasurementTarget, ...]
    action: str
    evidence_state: str = "MODEL_UNCERTAINTY_HEURISTIC_NOT_EMPIRICAL_CONFIDENCE"

    def as_dict(self) -> dict[str, object]:
        return {
            "winner_id": self.winner_id,
            "decision_confident_under_interval_heuristic": self.decision_confident_under_interval_heuristic,
            "ambiguous_candidate_ids": list(self.ambiguous_candidate_ids),
            "runner_up_score_gap": self.runner_up_score_gap,
            "winner_interval": self.winner_interval.as_dict() if self.winner_interval else None,
            "ambiguous_intervals": [item.as_dict() for item in self.ambiguous_intervals],
            "recommended_measurements": [item.as_dict() for item in self.recommended_measurements],
            "action": self.action,
            "evidence_state": self.evidence_state,
            "truth_boundary": (
                "Intervals are deterministic engineering heuristics derived from model uncertainty ratios, not calibrated statistical confidence intervals. "
                "BENCHMARK_MORE means the modeled decision is uncertainty-sensitive; it is not proof that the current winner is wrong."
            ),
        }


def _score_interval(candidate: CandidateResult) -> CandidateScoreInterval:
    uncertainty = max(0.0, candidate.uncertainty_ratio)
    radius = abs(candidate.score) * uncertainty
    return CandidateScoreInterval(
        candidate_id=candidate.id,
        score=candidate.score,
        uncertainty_ratio=uncertainty,
        lower=max(0.0, candidate.score - radius),
        upper=candidate.score + radius,
        prediction_source=candidate.prediction_source,
    )


def _measurement_targets(
    winner: CandidateResult,
    ambiguous: list[CandidateResult],
    *,
    max_recommendations: int,
) -> tuple[MeasurementTarget, ...]:
    if max_recommendations < 1:
        raise ValueError("max_recommendations must be positive")

    all_candidates = [winner, *ambiguous]
    target_candidates: dict[tuple[str, str], set[str]] = {}
    target_priority: dict[tuple[str, str], float] = {}
    target_bootstrap: dict[tuple[str, str], bool] = {}
    winner_score = winner.score

    for candidate in all_candidates:
        gap = max(0.0, candidate.score - winner_score)
        closeness = 1.0 / (1.0 + gap)
        for assignment in candidate.assignments:
            key = (assignment.primitive, assignment.query_kind.value)
            target_candidates.setdefault(key, set()).add(candidate.id)
            target_priority[key] = max(
                target_priority.get(key, 0.0),
                candidate.uncertainty_ratio * closeness,
            )
            target_bootstrap[key] = target_bootstrap.get(key, False) or (
                "BOOTSTRAP" in candidate.prediction_source
            )

    ranked: list[MeasurementTarget] = []
    for (primitive, operation), candidate_ids in target_candidates.items():
        bootstrap = target_bootstrap[(primitive, operation)]
        priority = target_priority[(primitive, operation)] + (0.25 if bootstrap else 0.0)
        reason = (
            "Bootstrap-derived cost contributes to overlapping winner/competitor score intervals."
            if bootstrap
            else "Calibrated/model-derived cost still contributes to overlapping winner/competitor score intervals."
        )
        ranked.append(
            MeasurementTarget(
                primitive=primitive,
                operation=operation,
                candidate_ids=tuple(sorted(candidate_ids)),
                priority=round(priority, 6),
                reason=reason,
            )
        )
    ranked.sort(key=lambda item: (-item.priority, item.primitive, item.operation))
    return tuple(ranked[:max_recommendations])


def assess_decision_confidence(
    result: SynthesisResult,
    *,
    interval_scale: float = 1.0,
    max_recommendations: int = 12,
) -> DecisionConfidenceAssessment:
    """Detect whether candidate uncertainty can plausibly change the modeled winner.

    MORPHEUS currently carries conservative scalar uncertainty ratios rather than
    a fully learned posterior. We therefore use interval overlap only as an
    *active measurement trigger*. It must not be interpreted as a frequentist or
    Bayesian confidence interval.
    """

    if interval_scale < 0:
        raise ValueError("interval_scale must be non-negative")
    if max_recommendations < 1:
        raise ValueError("max_recommendations must be positive")
    if result.winner is None:
        return DecisionConfidenceAssessment(
            winner_id=None,
            decision_confident_under_interval_heuristic=False,
            ambiguous_candidate_ids=(),
            runner_up_score_gap=None,
            winner_interval=None,
            ambiguous_intervals=(),
            recommended_measurements=(),
            action="NO_FEASIBLE_CANDIDATE",
        )

    feasible = [candidate for candidate in result.candidates if candidate.feasible]
    feasible.sort(key=lambda candidate: (candidate.score, candidate.id))
    winner = result.winner
    scaled_winner = CandidateResult.model_validate(
        {**winner.model_dump(mode="json"), "uncertainty_ratio": winner.uncertainty_ratio * interval_scale}
    )
    winner_interval = _score_interval(scaled_winner)

    ambiguous: list[CandidateResult] = []
    ambiguous_intervals: list[CandidateScoreInterval] = []
    for candidate in feasible:
        if candidate.id == winner.id:
            continue
        scaled = CandidateResult.model_validate(
            {**candidate.model_dump(mode="json"), "uncertainty_ratio": candidate.uncertainty_ratio * interval_scale}
        )
        interval = _score_interval(scaled)
        # A lower-is-better challenger remains decision-relevant if its plausible
        # lower bound reaches the winner's plausible upper bound.
        if interval.lower <= winner_interval.upper:
            ambiguous.append(candidate)
            ambiguous_intervals.append(interval)

    runner_up_gap = None
    if len(feasible) >= 2:
        runner_up_gap = max(0.0, feasible[1].score - winner.score)

    targets = _measurement_targets(
        winner,
        ambiguous,
        max_recommendations=max_recommendations,
    ) if ambiguous else ()
    confident = not ambiguous
    return DecisionConfidenceAssessment(
        winner_id=winner.id,
        decision_confident_under_interval_heuristic=confident,
        ambiguous_candidate_ids=tuple(candidate.id for candidate in ambiguous),
        runner_up_score_gap=runner_up_gap,
        winner_interval=winner_interval,
        ambiguous_intervals=tuple(ambiguous_intervals),
        recommended_measurements=targets,
        action="ACCEPT_MODELED_WINNER" if confident else "BENCHMARK_MORE",
    )
