from __future__ import annotations

from dataclasses import dataclass

from .engine import synthesize
from .models import SearchStrategy, WorkloadSpec


@dataclass(frozen=True)
class SearchQualityReport:
    theoretical_configurations: int
    exhaustive_evaluated: int
    beam_evaluated: int
    exhaustive_winner_id: str | None
    beam_winner_id: str | None
    exhaustive_winner_score: float | None
    beam_winner_score: float | None
    winner_matches_oracle: bool
    absolute_score_regret: float | None
    relative_score_regret: float | None
    search_reduction_ratio: float
    exhaustive_pareto_count: int
    beam_pareto_count: int
    pareto_id_coverage_ratio: float | None
    evidence_state: str = "SEARCH_HEURISTIC_EVALUATED_AGAINST_EXHAUSTIVE_MODEL_ORACLE"

    def as_dict(self) -> dict[str, object]:
        return {
            "theoretical_configurations": self.theoretical_configurations,
            "exhaustive_evaluated": self.exhaustive_evaluated,
            "beam_evaluated": self.beam_evaluated,
            "exhaustive_winner_id": self.exhaustive_winner_id,
            "beam_winner_id": self.beam_winner_id,
            "exhaustive_winner_score": self.exhaustive_winner_score,
            "beam_winner_score": self.beam_winner_score,
            "winner_matches_oracle": self.winner_matches_oracle,
            "absolute_score_regret": self.absolute_score_regret,
            "relative_score_regret": self.relative_score_regret,
            "search_reduction_ratio": self.search_reduction_ratio,
            "exhaustive_pareto_count": self.exhaustive_pareto_count,
            "beam_pareto_count": self.beam_pareto_count,
            "pareto_id_coverage_ratio": self.pareto_id_coverage_ratio,
            "evidence_state": self.evidence_state,
        }


def compare_beam_to_exhaustive(
    spec: WorkloadSpec,
    *,
    beam_width: int = 128,
    exhaustive_limit: int = 100_000,
) -> SearchQualityReport:
    """Compare beam search with an exhaustive *model* oracle on a bounded space.

    This evaluates search fidelity to MORPHEUS's own modeled objective. It does
    not establish that the cost model matches real hardware. Publication-grade
    claims require the separate held-out measurement evaluator as well.
    """

    if beam_width < 1:
        raise ValueError("beam_width must be positive")
    if exhaustive_limit < 1:
        raise ValueError("exhaustive_limit must be positive")

    exhaustive = synthesize(
        spec,
        strategy=SearchStrategy.EXHAUSTIVE,
        max_candidates=exhaustive_limit,
        beam_width=beam_width,
    )
    if exhaustive.search_summary is None:
        raise ValueError("exhaustive synthesis did not return search provenance")
    if exhaustive.search_summary.truncated:
        raise ValueError(
            "exhaustive oracle would be truncated; increase exhaustive_limit or use a smaller bounded workload"
        )

    beam = synthesize(
        spec,
        strategy=SearchStrategy.BEAM,
        max_candidates=min(exhaustive_limit, beam_width),
        beam_width=beam_width,
    )
    if beam.search_summary is None:
        raise ValueError("beam synthesis did not return search provenance")

    oracle_winner = exhaustive.winner
    beam_winner = beam.winner
    absolute_regret: float | None = None
    relative_regret: float | None = None
    winner_matches = False
    if oracle_winner is None and beam_winner is None:
        winner_matches = True
    elif oracle_winner is not None and beam_winner is not None:
        winner_matches = oracle_winner.id == beam_winner.id
        absolute_regret = max(0.0, beam_winner.score - oracle_winner.score)
        relative_regret = absolute_regret / abs(oracle_winner.score) if oracle_winner.score != 0 else None

    exhaustive_evaluated = exhaustive.search_summary.evaluated_configurations
    beam_evaluated = beam.search_summary.evaluated_configurations
    search_reduction = (
        1.0 - (beam_evaluated / exhaustive_evaluated)
        if exhaustive_evaluated > 0
        else 0.0
    )

    exhaustive_pareto_ids = {candidate.id for candidate in exhaustive.pareto_front}
    beam_pareto_ids = {candidate.id for candidate in beam.pareto_front}
    pareto_coverage = (
        len(exhaustive_pareto_ids & beam_pareto_ids) / len(exhaustive_pareto_ids)
        if exhaustive_pareto_ids
        else None
    )

    return SearchQualityReport(
        theoretical_configurations=exhaustive.search_summary.theoretical_configurations,
        exhaustive_evaluated=exhaustive_evaluated,
        beam_evaluated=beam_evaluated,
        exhaustive_winner_id=oracle_winner.id if oracle_winner else None,
        beam_winner_id=beam_winner.id if beam_winner else None,
        exhaustive_winner_score=oracle_winner.score if oracle_winner else None,
        beam_winner_score=beam_winner.score if beam_winner else None,
        winner_matches_oracle=winner_matches,
        absolute_score_regret=absolute_regret,
        relative_score_regret=relative_regret,
        search_reduction_ratio=search_reduction,
        exhaustive_pareto_count=len(exhaustive_pareto_ids),
        beam_pareto_count=len(beam_pareto_ids),
        pareto_id_coverage_ratio=pareto_coverage,
    )
