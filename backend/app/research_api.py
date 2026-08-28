from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .active_measurement import assess_decision_confidence
from .calibration import CALIBRATIONS
from .calibration_coverage import audit_calibration_coverage
from .engine import DEFAULT_BEAM_WIDTH, DEFAULT_MAX_CANDIDATES, synthesize
from .measurement_resolution import resolve_ambiguous_decision
from .models import SearchStrategy
from .parser import SpecParseError, parse_workload_text, semantic_hash
from .search_quality import compare_beam_to_exhaustive, compare_greedy_to_exhaustive


router = APIRouter(prefix="/api/v2/research", tags=["MORPHEUS research evidence"])
_SYNC_MEASUREMENT_MAX_RECORDS = 25_000
_SYNC_MEASUREMENT_MAX_WORK_UNITS = 5_000_000
_SYNC_COMPILE_TIMEOUT_SECONDS = 45
_SYNC_RUN_TIMEOUT_SECONDS = 45


class DecisionConfidenceRequest(BaseModel):
    spec_text: str = Field(min_length=1, max_length=256_000)
    strategy: SearchStrategy = SearchStrategy.AUTO
    max_candidates: int = Field(default=DEFAULT_MAX_CANDIDATES, ge=1, le=100_000)
    beam_width: int = Field(default=DEFAULT_BEAM_WIDTH, ge=1, le=4096)
    interval_scale: float = Field(default=1.0, ge=0, le=10)
    max_recommendations: int = Field(default=12, ge=1, le=100)


class ResolveDecisionRequest(BaseModel):
    spec_text: str = Field(min_length=1, max_length=256_000)
    strategy: SearchStrategy = SearchStrategy.AUTO
    max_candidates: int = Field(default=DEFAULT_MAX_CANDIDATES, ge=1, le=100_000)
    beam_width: int = Field(default=DEFAULT_BEAM_WIDTH, ge=1, le=4096)
    interval_scale: float = Field(default=1.0, ge=0, le=10)
    max_candidates_to_measure: int = Field(default=3, ge=2, le=3)
    operations: int = Field(default=1000, ge=1, le=20_000)
    repetitions: int = Field(default=3, ge=1, le=10)
    warmup: int = Field(default=1, ge=0, le=3)


class CompareHeuristicsRequest(BaseModel):
    spec_text: str = Field(min_length=1, max_length=256_000)
    beam_width: int = Field(default=DEFAULT_BEAM_WIDTH, ge=1, le=4096)
    exhaustive_limit: int = Field(default=100_000, ge=1, le=1_000_000)


def _parse(raw: str):
    try:
        return parse_workload_text(raw)
    except (SpecParseError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _synchronous_measurement_work_units(spec, request: ResolveDecisionRequest) -> int:
    passes = request.repetitions + request.warmup
    candidates = request.max_candidates_to_measure
    build_units = spec.record_count * passes * candidates
    route_units = request.operations * passes * max(1, len(spec.queries)) * candidates
    return build_units + route_units


@router.get("/calibration/coverage")
def active_calibration_coverage() -> dict[str, Any]:
    profile = CALIBRATIONS.active()
    if profile is None:
        raise HTTPException(status_code=404, detail="no active calibration profile")
    return audit_calibration_coverage(profile).as_dict()


@router.get("/calibration/coverage/{profile_id}")
def calibration_coverage(profile_id: str) -> dict[str, Any]:
    try:
        profile = CALIBRATIONS.get(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return audit_calibration_coverage(profile).as_dict()


@router.post("/decision-confidence")
def decision_confidence(request: DecisionConfidenceRequest) -> dict[str, Any]:
    spec = _parse(request.spec_text)
    result = synthesize(
        spec,
        strategy=request.strategy,
        max_candidates=request.max_candidates,
        beam_width=request.beam_width,
    )
    try:
        assessment = assess_decision_confidence(
            result,
            interval_scale=request.interval_scale,
            max_recommendations=request.max_recommendations,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "spec_hash": semantic_hash(spec),
        "winner_id": result.winner.id if result.winner else None,
        "search_summary": result.search_summary.model_dump(mode="json") if result.search_summary else None,
        "assessment": assessment.as_dict(),
        "evidence_state": assessment.evidence_state,
    }


@router.post("/decision-resolve")
def resolve_decision(request: ResolveDecisionRequest) -> dict[str, Any]:
    """Resolve an uncertainty-sensitive modeled decision with bounded local measurement.

    This synchronous research surface is deliberately small. It may compile and
    execute generated C++ only inside strict record, work and timeout budgets.
    Larger experiments belong in the offline research campaign where provenance
    artifacts and machine metadata are preserved.
    """

    spec = _parse(request.spec_text)
    if spec.record_count > _SYNC_MEASUREMENT_MAX_RECORDS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"synchronous active measurement is capped at {_SYNC_MEASUREMENT_MAX_RECORDS} records; "
                "use the offline generated-candidate validation campaign for larger workloads"
            ),
        )
    work_units = _synchronous_measurement_work_units(spec, request)
    if work_units > _SYNC_MEASUREMENT_MAX_WORK_UNITS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"requested active measurement budget is {work_units} work units, above the synchronous cap of "
                f"{_SYNC_MEASUREMENT_MAX_WORK_UNITS}; reduce operations/repetitions/routes or use the offline campaign"
            ),
        )

    result = synthesize(
        spec,
        strategy=request.strategy,
        max_candidates=request.max_candidates,
        beam_width=request.beam_width,
    )
    try:
        report = resolve_ambiguous_decision(
            spec,
            result,
            interval_scale=request.interval_scale,
            max_candidates_to_measure=request.max_candidates_to_measure,
            operations=request.operations,
            repetitions=request.repetitions,
            warmup=request.warmup,
            compile_timeout_seconds=_SYNC_COMPILE_TIMEOUT_SECONDS,
            run_timeout_seconds=_SYNC_RUN_TIMEOUT_SECONDS,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "spec_hash": semantic_hash(spec),
        "search_summary": result.search_summary.model_dump(mode="json") if result.search_summary else None,
        "report": report.as_dict(),
        "evidence_state": report.evidence_state,
        "execution_budget": {
            "estimated_work_units": work_units,
            "max_work_units": _SYNC_MEASUREMENT_MAX_WORK_UNITS,
            "max_records": _SYNC_MEASUREMENT_MAX_RECORDS,
            "compile_timeout_seconds_per_candidate": _SYNC_COMPILE_TIMEOUT_SECONDS,
            "run_timeout_seconds_per_candidate": _SYNC_RUN_TIMEOUT_SECONDS,
        },
        "execution_boundary": (
            "This endpoint can compile and execute a bounded generated benchmark locally. "
            "Its measurements are exploratory machine-local evidence, not publication-grade performance claims."
        ),
    }


@router.post("/search/compare-all")
def compare_search_heuristics(request: CompareHeuristicsRequest) -> dict[str, Any]:
    spec = _parse(request.spec_text)
    try:
        greedy = compare_greedy_to_exhaustive(
            spec,
            exhaustive_limit=request.exhaustive_limit,
        )
        beam = compare_beam_to_exhaustive(
            spec,
            beam_width=request.beam_width,
            exhaustive_limit=request.exhaustive_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "spec_hash": semantic_hash(spec),
        "greedy": greedy.as_dict(),
        "beam": beam.as_dict(),
        "evidence_state": "SEARCH_HEURISTICS_EVALUATED_AGAINST_EXHAUSTIVE_MODEL_ORACLE",
        "truth_boundary": (
            "Greedy/beam regret here is relative to MORPHEUS's exhaustive modeled objective on a tractable space. "
            "It is not empirical hardware regret unless the objective itself has been independently measured and validated."
        ),
    }
