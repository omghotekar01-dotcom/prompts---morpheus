from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .engine import DEFAULT_BEAM_WIDTH, DEFAULT_MAX_CANDIDATES, synthesize
from .hot_path_doctor import CURRENT_STRUCTURES, diagnose_hot_path, hot_path_doctor_options
from .hot_path_watch import watch_hot_path
from .models import SearchStrategy
from .parser import SpecParseError, parse_workload_text
from .storage import STORE
from .trace_intake import TraceIntakeError, normalize_trace_content


router = APIRouter(prefix="/api/v2/doctor", tags=["MORPHEUS hot path doctor"])


class HotPathDoctorRequest(BaseModel):
    spec_text: str = Field(min_length=1, max_length=256_000)
    current_structure: str = Field(default="custom_or_unknown", min_length=1, max_length=64)
    strategy: SearchStrategy = SearchStrategy.AUTO
    max_candidates: int = Field(default=DEFAULT_MAX_CANDIDATES, ge=1, le=100_000)
    beam_width: int = Field(default=DEFAULT_BEAM_WIDTH, ge=1, le=4096)


class TraceIntakeRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2_000_000)
    format_hint: str = Field(default="auto", min_length=1, max_length=16)
    key_field: str | None = Field(default=None, min_length=1, max_length=128)
    allow_invalid_rows: bool = False


class HotPathWatchRequest(BaseModel):
    spec_text: str = Field(min_length=1, max_length=256_000)
    current_structure: str = Field(default="custom_or_unknown", min_length=1, max_length=64)
    query_index: int = Field(default=0, ge=0, le=31)
    baseline_keys: list[int] = Field(min_length=2, max_length=100_000)
    observed_keys: list[int] = Field(min_length=2, max_length=100_000)
    threshold: float = Field(default=0.20, ge=0, le=1)
    strategy: SearchStrategy = SearchStrategy.AUTO
    max_candidates: int = Field(default=DEFAULT_MAX_CANDIDATES, ge=1, le=100_000)
    beam_width: int = Field(default=DEFAULT_BEAM_WIDTH, ge=1, le=4096)


@router.get("/hot-path/options")
def hot_path_options() -> dict[str, Any]:
    return hot_path_doctor_options()


@router.post("/hot-path/trace-intake")
def hot_path_trace_intake(request: TraceIntakeRequest) -> dict[str, Any]:
    try:
        report = normalize_trace_content(
            request.content,
            format_hint=request.format_hint,
            key_field=request.key_field,
            allow_invalid_rows=request.allow_invalid_rows,
        )
    except TraceIntakeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    STORE.record_event(
        "real_workload_trace_intake",
        "Normalized a bounded developer-supplied trace for Hot Path Watch",
        {
            "source_format": report.get("source_format"),
            "selected_key_field": report.get("selected_key_field"),
            "sample_count": report.get("sample_count"),
            "unique_key_count": report.get("unique_key_count"),
            "rejected_count": report.get("rejected_count"),
            "input_sha256": report.get("input_sha256"),
            "normalized_window_sha256": report.get("normalized_window_sha256"),
            "automatic_control_allowed": False,
        },
    )
    return report


@router.post("/hot-path/watch")
def hot_path_watch(request: HotPathWatchRequest) -> dict[str, Any]:
    if request.current_structure not in CURRENT_STRUCTURES:
        raise HTTPException(
            status_code=422,
            detail=(
                "current_structure must be one of: "
                + ", ".join(sorted(CURRENT_STRUCTURES))
            ),
        )
    try:
        report = watch_hot_path(
            request.spec_text,
            current_structure=request.current_structure,
            query_index=request.query_index,
            baseline_keys=request.baseline_keys,
            observed_keys=request.observed_keys,
            threshold=request.threshold,
            strategy=request.strategy,
            max_candidates=request.max_candidates,
            beam_width=request.beam_width,
        )
    except (SpecParseError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
    passport = report.get("freshness_passport") if isinstance(report.get("freshness_passport"), dict) else {}
    STORE.record_event(
        "hot_path_watch",
        "Hot Path Watch compared finite trace windows and re-evaluated the modeled recommendation",
        {
            "query_index": request.query_index,
            "current_structure": request.current_structure,
            "drifted": bool(report.get("drift", {}).get("drifted")) if isinstance(report.get("drift"), dict) else None,
            "action": decision.get("action"),
            "candidate_changed": decision.get("candidate_changed"),
            "route_primitive_changed": decision.get("route_primitive_changed"),
            "freshness_state": passport.get("freshness_state"),
            "passport_sha256": passport.get("passport_sha256"),
            "rollout_disposition": passport.get("rollout_disposition"),
            "automatic_control_allowed": False,
        },
    )
    return report


@router.post("/hot-path")
def hot_path_diagnosis(request: HotPathDoctorRequest) -> dict[str, Any]:
    if request.current_structure not in CURRENT_STRUCTURES:
        raise HTTPException(
            status_code=422,
            detail=(
                "current_structure must be one of: "
                + ", ".join(sorted(CURRENT_STRUCTURES))
            ),
        )
    try:
        spec = parse_workload_text(request.spec_text)
        result = synthesize(
            spec,
            strategy=request.strategy,
            max_candidates=request.max_candidates,
            beam_width=request.beam_width,
        )
        report = diagnose_hot_path(
            spec,
            result,
            current_structure=request.current_structure,
        )
    except (SpecParseError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    STORE.record_event(
        "hot_path_diagnosis",
        "Hot Path Doctor produced an evidence-bounded application data-structure recommendation",
        {
            "workload_name": spec.name,
            "current_structure": request.current_structure,
            "winner_candidate_id": result.winner.id if result.winner else None,
            "evidence_state": result.evidence_state,
            "next_gate": report.get("next_gate"),
            "automatic_control_allowed": False,
        },
    )
    return report
