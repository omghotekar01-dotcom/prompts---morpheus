from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .active_measurement import assess_decision_confidence
from .calibration import CALIBRATIONS
from .calibration_coverage import audit_calibration_coverage
from .engine import DEFAULT_BEAM_WIDTH, DEFAULT_MAX_CANDIDATES, synthesize
from .models import SearchStrategy
from .parser import SpecParseError, parse_workload_text, semantic_hash
from .search_quality import compare_beam_to_exhaustive, compare_greedy_to_exhaustive


router = APIRouter(prefix="/api/v2/research", tags=["MORPHEUS research evidence"])


class DecisionConfidenceRequest(BaseModel):
    spec_text: str = Field(min_length=1, max_length=256_000)
    strategy: SearchStrategy = SearchStrategy.AUTO
    max_candidates: int = Field(default=DEFAULT_MAX_CANDIDATES, ge=1, le=100_000)
    beam_width: int = Field(default=DEFAULT_BEAM_WIDTH, ge=1, le=4096)
    interval_scale: float = Field(default=1.0, ge=0, le=10)
    max_recommendations: int = Field(default=12, ge=1, le=100)


class CompareHeuristicsRequest(BaseModel):
    spec_text: str = Field(min_length=1, max_length=256_000)
    beam_width: int = Field(default=DEFAULT_BEAM_WIDTH, ge=1, le=4096)
    exhaustive_limit: int = Field(default=100_000, ge=1, le=1_000_000)


def _parse(raw: str):
    try:
        return parse_workload_text(raw)
    except (SpecParseError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
