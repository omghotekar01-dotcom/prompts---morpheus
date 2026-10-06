from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .engine import DEFAULT_BEAM_WIDTH, DEFAULT_MAX_CANDIDATES, synthesize
from .hot_path_doctor import CURRENT_STRUCTURES, diagnose_hot_path, hot_path_doctor_options
from .models import SearchStrategy
from .parser import SpecParseError, parse_workload_text
from .storage import STORE


router = APIRouter(prefix="/api/v2/doctor", tags=["MORPHEUS hot path doctor"])


class HotPathDoctorRequest(BaseModel):
    spec_text: str = Field(min_length=1, max_length=256_000)
    current_structure: str = Field(default="custom_or_unknown", min_length=1, max_length=64)
    strategy: SearchStrategy = SearchStrategy.AUTO
    max_candidates: int = Field(default=DEFAULT_MAX_CANDIDATES, ge=1, le=100_000)
    beam_width: int = Field(default=DEFAULT_BEAM_WIDTH, ge=1, le=4096)


@router.get("/hot-path/options")
def hot_path_options() -> dict[str, Any]:
    return hot_path_doctor_options()


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
