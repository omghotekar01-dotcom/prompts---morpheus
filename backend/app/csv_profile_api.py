from __future__ import annotations

"""Real user-data CSV profiling and optional workload synthesis API."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .engine import DEFAULT_BEAM_WIDTH, DEFAULT_MAX_CANDIDATES, synthesize
from .dataset_catalog import catalog_inventory, query_options
from .artifact_codegen import ArtifactCodegenError, generate_verified_header
from .models import Constraints, ObjectiveWeights, QuerySpec, SearchStrategy, WorkloadSpec
from .native_csv_profile import (
    CsvProfilerMissing,
    CsvProfilingError,
    profile_submitted_csv,
)
from .native_search_backend import NativeSearchError


router = APIRouter(prefix="/api/v2/data", tags=["Native C++ data profiling"])


@router.get("/catalog")
def describe_native_catalog():
    return {"primitives": catalog_inventory(), "catalog_evidence": "IMPLEMENTATION_REGISTRY_WITH_BOOTSTRAP_PRIORS"}


class CsvProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    csv_text: str = Field(min_length=1, max_length=1_000_000)
    # Supplying records does not reveal how they will be queried. An optional
    # operation mix is explicit user input, never fabricated by the system.
    queries: list[QuerySpec] | None = Field(default=None, max_length=32)
    constraints: Constraints = Field(default_factory=Constraints)
    objective: ObjectiveWeights = Field(default_factory=ObjectiveWeights)
    strategy: SearchStrategy = SearchStrategy.AUTO
    max_candidates: int = Field(default=DEFAULT_MAX_CANDIDATES, ge=1, le=10000)
    beam_width: int = Field(default=DEFAULT_BEAM_WIDTH, ge=1, le=4096)


@router.post("/profile-csv")
def profile_csv(request: CsvProfileRequest):
    try:
        measured = profile_submitted_csv(request.csv_text)
    except CsvProfilingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CsvProfilerMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    result = {"profile": measured, "synthesis": None, "options_by_query": [], "generated_artifact": None}
    if request.queries is None or len(request.queries) == 0:
        return result
    try:
        spec = WorkloadSpec.model_validate({
            "version": "mws-0.1",
            "name": "submitted_csv_workload",
            "record_count": measured["record_count"],
            "fields": measured["fields"],
            "queries": [query.model_dump(mode="json") for query in request.queries],
            "constraints": request.constraints.model_dump(mode="json"),
            "objective": request.objective.model_dump(mode="json"),
        })
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result["options_by_query"] = query_options(spec)
    try:
        synthesis = synthesize(
            spec, strategy=request.strategy,
            max_candidates=request.max_candidates,
            beam_width=request.beam_width,
        )
    except NativeSearchError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    result["synthesis"] = synthesis.model_dump(mode="json")
    if synthesis.winner is not None:
        try:
            code = generate_verified_header(spec, synthesis.winner)
            result["generated_artifact"] = {
                "file_name": code.header_name,
                "language": "C++20",
                "source": code.header_source,
                "candidate_id": synthesis.winner.id,
                "status": "GENERATED_NOT_COMPILE_OR_BEHAVIOR_VERIFIED",
                "requires": "MORPHEUS core/include headers and a C++20 compiler",
            }
        except ArtifactCodegenError as exc:
            result["generated_artifact_error"] = str(exc)
    return result
