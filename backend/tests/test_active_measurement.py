from __future__ import annotations

from app.active_measurement import assess_decision_confidence
from app.models import Assignment, CandidateResult, QueryKind, SynthesisResult


def _candidate(candidate_id: str, score: float, uncertainty: float, primitive: str) -> CandidateResult:
    return CandidateResult(
        id=candidate_id,
        assignments=[
            Assignment(
                query_index=0,
                query_kind=QueryKind.POINT_LOOKUP,
                field="id",
                primitive=primitive,
            )
        ],
        unique_primitives=[primitive],
        predicted_latency_us=score,
        predicted_memory_mb=1.0,
        predicted_build_ms=1.0,
        predicted_update_us=0.1,
        score=score,
        feasible=True,
        prediction_source="BOOTSTRAP_PRIOR",
        uncertainty_ratio=uncertainty,
    )


def test_overlapping_score_intervals_trigger_benchmark_more() -> None:
    winner = _candidate("winner", 1.0, 0.20, "robin_hood_hash")
    challenger = _candidate("challenger", 1.1, 0.20, "ordered_tree")
    result = SynthesisResult(spec_hash="a" * 64, winner=winner, candidates=[winner, challenger])
    assessment = assess_decision_confidence(result)
    assert assessment.action == "BENCHMARK_MORE"
    assert not assessment.decision_confident_under_interval_heuristic
    assert assessment.ambiguous_candidate_ids == ("challenger",)
    assert assessment.recommended_measurements
    assert assessment.recommended_measurements[0].priority > 0
    assert "not calibrated statistical confidence intervals" in assessment.as_dict()["truth_boundary"]


def test_separated_intervals_accept_modeled_winner_without_fake_confidence() -> None:
    winner = _candidate("winner", 1.0, 0.01, "robin_hood_hash")
    challenger = _candidate("challenger", 2.0, 0.01, "ordered_tree")
    result = SynthesisResult(spec_hash="b" * 64, winner=winner, candidates=[winner, challenger])
    assessment = assess_decision_confidence(result)
    assert assessment.action == "ACCEPT_MODELED_WINNER"
    assert assessment.decision_confident_under_interval_heuristic
    assert assessment.ambiguous_candidate_ids == ()
    assert assessment.recommended_measurements == ()


def test_interval_scale_zero_disables_uncertainty_overlap_radius() -> None:
    winner = _candidate("winner", 1.0, 0.8, "robin_hood_hash")
    challenger = _candidate("challenger", 1.1, 0.8, "ordered_tree")
    result = SynthesisResult(spec_hash="c" * 64, winner=winner, candidates=[winner, challenger])
    assessment = assess_decision_confidence(result, interval_scale=0)
    assert assessment.action == "ACCEPT_MODELED_WINNER"


def test_no_feasible_winner_is_distinct_from_low_confidence() -> None:
    result = SynthesisResult(spec_hash="d" * 64, winner=None, candidates=[])
    assessment = assess_decision_confidence(result)
    assert assessment.action == "NO_FEASIBLE_CANDIDATE"
    assert assessment.winner_id is None
    assert assessment.recommended_measurements == ()
