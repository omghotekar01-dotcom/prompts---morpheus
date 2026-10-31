from __future__ import annotations

"""Real user-data CSV profiling and optional workload synthesis API."""

from fastapi import APIRouter, HTTPException
from .dataset_input import excel_to_csv, normalize_csv
from .native_csv_probe import page_submitted_csv, probe_submitted_csv
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
from .java_plan_scorer import JavaPlanScorerError


router = APIRouter(prefix="/api/v2/data", tags=["Native C++ data profiling"])


@router.get("/catalog")
def describe_native_catalog():
    return {"primitives": catalog_inventory(), "catalog_evidence": "IMPLEMENTATION_REGISTRY_WITH_BOOTSTRAP_PRIORS"}


class CsvProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    csv_text: str | None = Field(default=None, max_length=15_000_000)
    xlsx_base64: str | None = Field(default=None, max_length=21_000_000)
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
    if bool(request.csv_text) == bool(request.xlsx_base64):
        raise HTTPException(status_code=422, detail="Supply exactly one: csv_text or xlsx_base64")
    try:
        prepared = (excel_to_csv(request.xlsx_base64) if request.xlsx_base64 is not None
                    else normalize_csv(request.csv_text))
        measured = profile_submitted_csv(prepared.csv_text)
    except (CsvProfilingError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (CsvProfilerMissing, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    measured["source_sha256"] = prepared.source_sha256
    measured["source_kind"] = prepared.source_kind
    measured["worksheet"] = prepared.worksheet
    for item, original_name in zip(measured["fields"], prepared.source_columns, strict=True):
        item["source_name"] = original_name

    result = {"profile": measured, "synthesis": None, "options_by_query": [], "generated_artifact": None}
    if request.queries is None or len(request.queries) == 0:
        return result
    try:
        spec = WorkloadSpec.model_validate({
            "version": "mws-0.1",
            "name": "submitted_csv_workload",
            "record_count": measured["record_count"],
            "fields": [{key: field[key] for key in ("name", "type", "cardinality")} for field in measured["fields"]],
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
    except (NativeSearchError, JavaPlanScorerError) as exc:
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


class CsvProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csv_text: str | None = Field(default=None, max_length=15_000_000)
    xlsx_base64: str | None = Field(default=None, max_length=21_000_000)
    field: str = Field(min_length=1, max_length=128)
    operation: str = Field(pattern=r"^(point_lookup|filter|prefix_search|range_scan)$")
    value: str = Field(max_length=4096)
    upper_value: str | None = Field(default=None, max_length=4096)
    preview_limit: int = Field(default=20, ge=1, le=50)


@router.post("/probe-csv")
def reference_scan_csv(request: CsvProbeRequest):
    if bool(request.csv_text) == bool(request.xlsx_base64):
        raise HTTPException(status_code=422, detail="Supply exactly one dataset")
    try:
        prepared = (excel_to_csv(request.xlsx_base64) if request.xlsx_base64 is not None
                    else normalize_csv(request.csv_text))
        if request.field not in prepared.canonical_columns:
            raise ValueError("Selected field is not a column of this dataset")
        if request.operation == "range_scan" and request.upper_value is None:
            raise ValueError("Range search requires an upper bound")
        result = probe_submitted_csv(
            prepared.csv_text, prepared.canonical_columns.index(request.field),
            request.operation, request.value, request.upper_value or "",
            request.preview_limit,
        )
    except (CsvProfilingError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (CsvProfilerMissing, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    result["field"] = request.field
    result["source_sha256"] = prepared.source_sha256
    result["source_columns"] = prepared.source_columns
    return result


class CsvPageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csv_text: str | None = Field(default=None, max_length=15_000_000)
    xlsx_base64: str | None = Field(default=None, max_length=21_000_000)
    offset: int = Field(default=0, ge=0, le=100_000)
    limit: int = Field(default=20, ge=1, le=50)


@router.post("/page-csv")
def browse_real_dataset(request: CsvPageRequest):
    if bool(request.csv_text) == bool(request.xlsx_base64):
        raise HTTPException(status_code=422, detail="Supply exactly one dataset")
    try:
        prepared = (excel_to_csv(request.xlsx_base64) if request.xlsx_base64 is not None
                    else normalize_csv(request.csv_text))
        result = page_submitted_csv(prepared.csv_text, request.offset, request.limit)
    except (ValueError, CsvProfilingError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (CsvProfilerMissing, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    result["source_columns"] = prepared.source_columns
    result["source_sha256"] = prepared.source_sha256
    return result
