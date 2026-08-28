from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .active_measurement import DecisionConfidenceAssessment, assess_decision_confidence
from .candidate_benchmark import CandidateBenchmarkResult, benchmark_generated_candidate
from .candidate_validation import CandidateValidationPoint, build_candidate_validation_point
from .models import AccessDistribution, CandidateResult, QueryKind, SynthesisResult, WorkloadSpec


BenchmarkRunner = Callable[..., CandidateBenchmarkResult]
_MUTATIONS = {QueryKind.INSERT, QueryKind.UPDATE, QueryKind.DELETE}


@dataclass(frozen=True)
class MeasuredCandidateDecision:
    candidate_id: str
    modeled_score: float
    predicted_query_latency_us: float
    measured_weighted_query_latency_us: float | None
    benchmark_success: bool
    benchmark_evidence_state: str
    configuration_ir_hash: str
    validation_evidence_state: str | None
    failure_reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "modeled_score": self.modeled_score,
            "predicted_query_latency_us": self.predicted_query_latency_us,
            "measured_weighted_query_latency_us": self.measured_weighted_query_latency_us,
            "benchmark_success": self.benchmark_success,
            "benchmark_evidence_state": self.benchmark_evidence_state,
            "configuration_ir_hash": self.configuration_ir_hash,
            "validation_evidence_state": self.validation_evidence_state,
            "failure_reason": self.failure_reason,
        }


@dataclass(frozen=True)
class MeasurementResolutionReport:
    modeled_winner_id: str | None
    resolved_winner_id: str | None
    action: str
    confidence_assessment: DecisionConfidenceAssessment
    measured_candidates: tuple[MeasuredCandidateDecision, ...]
    empirical_selection_allowed: bool
    empirical_selection_reason: str
    evidence_state: str

    def as_dict(self) -> dict[str, object]:
        return {
            "modeled_winner_id": self.modeled_winner_id,
            "resolved_winner_id": self.resolved_winner_id,
            "action": self.action,
            "confidence_assessment": self.confidence_assessment.as_dict(),
            "measured_candidates": [item.as_dict() for item in self.measured_candidates],
            "empirical_selection_allowed": self.empirical_selection_allowed,
            "empirical_selection_reason": self.empirical_selection_reason,
            "evidence_state": self.evidence_state,
            "truth_boundary": (
                "A resolved winner is changed from the modeled winner only for a read-only, latency-only objective with no p99 proxy constraint, "
                "after successful same-scale generated-candidate measurements of every finalist selected by the uncertainty trigger. "
                "The empirical winner is local to that measured finalist set and executing machine; it is not a global hardware-independent optimum."
            ),
        }


def _has_nonuniform_access(spec: WorkloadSpec) -> bool:
    return any(query.distribution.kind != AccessDistribution.UNIFORM for query in spec.queries)


def _empirical_selection_policy(spec: WorkloadSpec) -> tuple[bool, str]:
    if _has_nonuniform_access(spec):
        return False, "declared nonuniform access requires a distribution-aware generated-candidate benchmark"
    if any(query.kind in _MUTATIONS for query in spec.queries):
        return False, "mutation-declaring workloads do not yet have operation-specific end-to-end validation"
    if spec.constraints.p99_latency_us is not None:
        return False, "the candidate harness measures repeated medians, not a p99 latency distribution"
    if spec.objective.memory != 0 or spec.objective.update != 0 or spec.objective.build != 0:
        return False, "non-latency objective components are not all measured end-to-end by this resolver"
    if spec.objective.latency <= 0:
        return False, "latency objective weight must be positive for measured latency selection"
    return True, "read-only latency-only objective can be compared using measured weighted query latency"


def _candidate_map(result: SynthesisResult) -> dict[str, CandidateResult]:
    return {candidate.id: candidate for candidate in result.candidates if candidate.feasible}


def _selected_candidates(
    result: SynthesisResult,
    assessment: DecisionConfidenceAssessment,
    *,
    max_candidates_to_measure: int,
) -> list[CandidateResult]:
    if max_candidates_to_measure < 2:
        raise ValueError("max_candidates_to_measure must be at least 2")
    if result.winner is None:
        return []
    candidate_by_id = _candidate_map(result)
    selected = [result.winner]
    ambiguous = [
        candidate_by_id[candidate_id]
        for candidate_id in assessment.ambiguous_candidate_ids
        if candidate_id in candidate_by_id and candidate_id != result.winner.id
    ]
    ambiguous.sort(key=lambda candidate: (candidate.score, candidate.predicted_latency_us, candidate.id))
    selected.extend(ambiguous[: max_candidates_to_measure - 1])
    return selected


def _measured_record(
    spec: WorkloadSpec,
    candidate: CandidateResult,
    benchmark: CandidateBenchmarkResult,
) -> tuple[MeasuredCandidateDecision, CandidateValidationPoint | None]:
    if not benchmark.success:
        return (
            MeasuredCandidateDecision(
                candidate_id=candidate.id,
                modeled_score=candidate.score,
                predicted_query_latency_us=candidate.predicted_latency_us,
                measured_weighted_query_latency_us=None,
                benchmark_success=False,
                benchmark_evidence_state=benchmark.evidence_state,
                configuration_ir_hash=benchmark.configuration_ir_hash,
                validation_evidence_state=None,
                failure_reason=(benchmark.compile_stderr or benchmark.run_stderr or benchmark.evidence_state)[-2000:],
            ),
            None,
        )
    try:
        point = build_candidate_validation_point(spec, candidate, benchmark)
    except ValueError as exc:
        return (
            MeasuredCandidateDecision(
                candidate_id=candidate.id,
                modeled_score=candidate.score,
                predicted_query_latency_us=candidate.predicted_latency_us,
                measured_weighted_query_latency_us=None,
                benchmark_success=True,
                benchmark_evidence_state=benchmark.evidence_state,
                configuration_ir_hash=benchmark.configuration_ir_hash,
                validation_evidence_state=None,
                failure_reason=str(exc),
            ),
            None,
        )
    return (
        MeasuredCandidateDecision(
            candidate_id=candidate.id,
            modeled_score=candidate.score,
            predicted_query_latency_us=candidate.predicted_latency_us,
            measured_weighted_query_latency_us=point.measured_weighted_query_latency_us,
            benchmark_success=True,
            benchmark_evidence_state=benchmark.evidence_state,
            configuration_ir_hash=benchmark.configuration_ir_hash,
            validation_evidence_state=point.evidence_state,
        ),
        point,
    )


def resolve_ambiguous_decision(
    spec: WorkloadSpec,
    result: SynthesisResult,
    *,
    interval_scale: float = 1.0,
    max_candidates_to_measure: int = 3,
    operations: int = 2000,
    repetitions: int = 5,
    warmup: int = 1,
    compile_timeout_seconds: int = 60,
    run_timeout_seconds: int = 60,
    benchmark_runner: BenchmarkRunner = benchmark_generated_candidate,
) -> MeasurementResolutionReport:
    """Execute active measurement only when modeled uncertainty makes the winner decision-sensitive.

    The resolver is deliberately conservative. It never treats local benchmark
    medians as a universal cost oracle, and it does not replace a multi-objective
    modeled decision with a latency-only measurement. Its strongest automatic
    action is a local finalist tie-break for read-only latency-only workloads.
    """

    if operations < 1 or repetitions < 1 or warmup < 0:
        raise ValueError("operations/repetitions must be positive and warmup non-negative")
    if compile_timeout_seconds < 1 or run_timeout_seconds < 1:
        raise ValueError("compile and run timeouts must be positive")
    assessment = assess_decision_confidence(result, interval_scale=interval_scale)
    modeled_winner_id = result.winner.id if result.winner else None

    if result.winner is None:
        return MeasurementResolutionReport(
            modeled_winner_id=None,
            resolved_winner_id=None,
            action="NO_FEASIBLE_CANDIDATE",
            confidence_assessment=assessment,
            measured_candidates=(),
            empirical_selection_allowed=False,
            empirical_selection_reason="no feasible modeled candidate exists",
            evidence_state="NO_MEASUREMENT_PERFORMED",
        )

    if assessment.action != "BENCHMARK_MORE":
        allowed, reason = _empirical_selection_policy(spec)
        return MeasurementResolutionReport(
            modeled_winner_id=modeled_winner_id,
            resolved_winner_id=modeled_winner_id,
            action="ACCEPT_MODELED_WINNER_WITHOUT_ACTIVE_MEASUREMENT",
            confidence_assessment=assessment,
            measured_candidates=(),
            empirical_selection_allowed=allowed,
            empirical_selection_reason=reason,
            evidence_state="MODEL_DECISION_NOT_INTERVAL_AMBIGUOUS",
        )

    # Until the generated benchmark consumes the declared skew exactly, do not
    # run a uniform benchmark and attach those measurements to a nonuniform MWS.
    if _has_nonuniform_access(spec):
        return MeasurementResolutionReport(
            modeled_winner_id=modeled_winner_id,
            resolved_winner_id=modeled_winner_id,
            action="DISTRIBUTION_AWARE_MEASUREMENT_REQUIRED",
            confidence_assessment=assessment,
            measured_candidates=(),
            empirical_selection_allowed=False,
            empirical_selection_reason=(
                "the generated-candidate benchmark has not yet implemented the declared nonuniform access distribution"
            ),
            evidence_state="NONUNIFORM_WORKLOAD_NOT_MEASURED_BY_UNIFORM_HARNESS",
        )

    selected = _selected_candidates(
        result,
        assessment,
        max_candidates_to_measure=max_candidates_to_measure,
    )
    measured: list[MeasuredCandidateDecision] = []
    validation_points: list[CandidateValidationPoint] = []
    for candidate in selected:
        benchmark = benchmark_runner(
            spec,
            candidate,
            record_count=spec.record_count,
            operations=operations,
            repetitions=repetitions,
            warmup=warmup,
            compile_timeout_seconds=compile_timeout_seconds,
            run_timeout_seconds=run_timeout_seconds,
        )
        record, validation = _measured_record(spec, candidate, benchmark)
        measured.append(record)
        if validation is not None:
            validation_points.append(validation)

    allowed, reason = _empirical_selection_policy(spec)
    complete = len(validation_points) == len(selected) and len(selected) >= 2
    if not complete:
        return MeasurementResolutionReport(
            modeled_winner_id=modeled_winner_id,
            resolved_winner_id=modeled_winner_id,
            action="ACTIVE_MEASUREMENT_INCOMPLETE_KEEP_MODELED_WINNER",
            confidence_assessment=assessment,
            measured_candidates=tuple(measured),
            empirical_selection_allowed=allowed,
            empirical_selection_reason=reason,
            evidence_state="PARTIAL_LOCAL_GENERATED_CANDIDATE_MEASUREMENT",
        )

    if not allowed:
        return MeasurementResolutionReport(
            modeled_winner_id=modeled_winner_id,
            resolved_winner_id=modeled_winner_id,
            action="MEASUREMENTS_COLLECTED_REVIEW_REQUIRED",
            confidence_assessment=assessment,
            measured_candidates=tuple(measured),
            empirical_selection_allowed=False,
            empirical_selection_reason=reason,
            evidence_state="LOCAL_GENERATED_CANDIDATE_MEASUREMENTS_NOT_FULL_OBJECTIVE",
        )

    empirical = min(
        validation_points,
        key=lambda point: (point.measured_weighted_query_latency_us, point.candidate_id),
    )
    changed = empirical.candidate_id != modeled_winner_id
    return MeasurementResolutionReport(
        modeled_winner_id=modeled_winner_id,
        resolved_winner_id=empirical.candidate_id,
        action="EMPIRICAL_FINALIST_SWITCH" if changed else "EMPIRICAL_FINALIST_CONFIRMED",
        confidence_assessment=assessment,
        measured_candidates=tuple(measured),
        empirical_selection_allowed=True,
        empirical_selection_reason=reason,
        evidence_state="LOCAL_SAME_SCALE_GENERATED_CANDIDATE_FINALIST_DECISION",
    )
