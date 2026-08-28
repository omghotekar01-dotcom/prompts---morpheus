from __future__ import annotations

from dataclasses import dataclass

from .engine import synthesize
from .models import SearchStrategy, WorkloadSpec


@dataclass(frozen=True)
class SearchQualityReport:
    heuristic_strategy: str
    theoretical_configurations: int
    exhaustive_evaluated: int
    heuristic_evaluated: int
    exhaustive_winner_id: str | None
    heuristic_winner_id: str | None
    exhaustive_winner_score: float | None
    heuristic_winner_score: float | None
    winner_matches_oracle: bool
    absolute_score_regret: float | None
    relative_score_regret: float | None
    search_reduction_ratio: float
    exhaustive_pareto_count: int
    heuristic_pareto_count: int
    pareto_id_coverage_ratio: float | None
    evidence_state: str = "SEARCH_HEURISTIC_EVALUATED_AGAINST_EXHAUSTIVE_MODEL_ORACLE"

    # Backward-compatible beam field aliases keep existing API/tests stable while
    # the report becomes strategy-generic for RQ3.
    @property
    def beam_evaluated(self) -> int:
        return self.heuristic_evaluated

    @property
    def beam_winner_id(self) -> str | None:
        return self.heuristic_winner_id

    @property
    def beam_winner_score(self) -> float | None:
        return self.heuristic_winner_score

    @property
    def beam_pareto_count(self) -> int:
        return self.heuristic_pareto_count

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "heuristic_strategy": self.heuristic_strategy,
            "theoretical_configurations": self.theoretical_configurations,
            "exhaustive_evaluated": self.exhaustive_evaluated,
            "heuristic_evaluated": self.heuristic_evaluated,
            "exhaustive_winner_id": self.exhaustive_winner_id,
            "heuristic_winner_id": self.heuristic_winner_id,
            "exhaustive_winner_score": self.exhaustive_winner_score,
            "heuristic_winner_score": self.heuristic_winner_score,
            "winner_matches_oracle": self.winner_matches_oracle,
            "absolute_score_regret": self.absolute_score_regret,
            "relative_score_regret": self.relative_score_regret,
            "search_reduction_ratio": self.search_reduction_ratio,
            "exhaustive_pareto_count": self.exhaustive_pareto_count,
            "heuristic_pareto_count": self.heuristic_pareto_count,
            "pareto_id_coverage_ratio": self.pareto_id_coverage_ratio,
            "evidence_state": self.evidence_state,
        }
        if self.heuristic_strategy == SearchStrategy.BEAM.value:
            payload.update(
                {
                    "beam_evaluated": self.heuristic_evaluated,
                    "beam_winner_id": self.heuristic_winner_id,
                    "beam_winner_score": self.heuristic_winner_score,
                    "beam_pareto_count": self.heuristic_pareto_count,
                }
            )
        return payload


def compare_strategy_to_exhaustive(
    spec: WorkloadSpec,
    *,
    strategy: SearchStrategy,
    beam_width: int = 128,
    exhaustive_limit: int = 100_000,
) -> SearchQualityReport:
    """Compare a bounded heuristic with exhaustive *model* oracle enumeration.

    This evaluates search fidelity to MORPHEUS's modeled objective. It does not
    establish cost-model accuracy on hardware. `GREEDY` is a deliberately cheap
    myopic baseline and `BEAM` is the main bounded heuristic. AUTO/EXHAUSTIVE are
    rejected here because they do not define the heuristic side of this RQ3
    comparison.
    """

    if strategy not in {SearchStrategy.GREEDY, SearchStrategy.BEAM}:
        raise ValueError("strategy comparison supports only greedy or beam")
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

    heuristic = synthesize(
        spec,
        strategy=strategy,
        max_candidates=min(exhaustive_limit, beam_width) if strategy == SearchStrategy.BEAM else 1,
        beam_width=beam_width,
    )
    if heuristic.search_summary is None:
        raise ValueError("heuristic synthesis did not return search provenance")

    oracle_winner = exhaustive.winner
    heuristic_winner = heuristic.winner
    absolute_regret: float | None = None
    relative_regret: float | None = None
    winner_matches = False
    if oracle_winner is None and heuristic_winner is None:
        winner_matches = True
    elif oracle_winner is not None and heuristic_winner is not None:
        winner_matches = oracle_winner.id == heuristic_winner.id
        absolute_regret = max(0.0, heuristic_winner.score - oracle_winner.score)
        relative_regret = absolute_regret / abs(oracle_winner.score) if oracle_winner.score != 0 else None

    exhaustive_evaluated = exhaustive.search_summary.evaluated_configurations
    heuristic_evaluated = heuristic.search_summary.evaluated_configurations
    search_reduction = (
        1.0 - (heuristic_evaluated / exhaustive_evaluated)
        if exhaustive_evaluated > 0
        else 0.0
    )

    exhaustive_pareto_ids = {candidate.id for candidate in exhaustive.pareto_front}
    heuristic_pareto_ids = {candidate.id for candidate in heuristic.pareto_front}
    pareto_coverage = (
        len(exhaustive_pareto_ids & heuristic_pareto_ids) / len(exhaustive_pareto_ids)
        if exhaustive_pareto_ids
        else None
    )

    return SearchQualityReport(
        heuristic_strategy=strategy.value,
        theoretical_configurations=exhaustive.search_summary.theoretical_configurations,
        exhaustive_evaluated=exhaustive_evaluated,
        heuristic_evaluated=heuristic_evaluated,
        exhaustive_winner_id=oracle_winner.id if oracle_winner else None,
        heuristic_winner_id=heuristic_winner.id if heuristic_winner else None,
        exhaustive_winner_score=oracle_winner.score if oracle_winner else None,
        heuristic_winner_score=heuristic_winner.score if heuristic_winner else None,
        winner_matches_oracle=winner_matches,
        absolute_score_regret=absolute_regret,
        relative_score_regret=relative_regret,
        search_reduction_ratio=search_reduction,
        exhaustive_pareto_count=len(exhaustive_pareto_ids),
        heuristic_pareto_count=len(heuristic_pareto_ids),
        pareto_id_coverage_ratio=pareto_coverage,
    )


def compare_beam_to_exhaustive(
    spec: WorkloadSpec,
    *,
    beam_width: int = 128,
    exhaustive_limit: int = 100_000,
) -> SearchQualityReport:
    return compare_strategy_to_exhaustive(
        spec,
        strategy=SearchStrategy.BEAM,
        beam_width=beam_width,
        exhaustive_limit=exhaustive_limit,
    )


def compare_greedy_to_exhaustive(
    spec: WorkloadSpec,
    *,
    exhaustive_limit: int = 100_000,
) -> SearchQualityReport:
    return compare_strategy_to_exhaustive(
        spec,
        strategy=SearchStrategy.GREEDY,
        beam_width=1,
        exhaustive_limit=exhaustive_limit,
    )
