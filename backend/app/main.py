from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .artifact_codegen import ArtifactCodegenError, generate_verified_header
from .catalog import PRIMITIVES
from .engine import synthesize
from .models import ObservedWorkloadSnapshot
from .parser import SpecParseError, canonical_dict, parse_workload_text, semantic_hash
from .runtime import decide_adaptation


class SpecTextRequest(BaseModel):
    spec_text: str = Field(min_length=1)


class AdaptationRequest(BaseModel):
    snapshot: ObservedWorkloadSnapshot
    current_predicted_latency_us: float = Field(gt=0)
    alternative_predicted_latency_us: float = Field(gt=0)
    estimated_switching_cost_us: float = Field(ge=0)
    lambda_factor: float = Field(default=1.5, gt=0)
    safety_margin_ratio: float = Field(default=0.10, ge=0, le=1)


app = FastAPI(
    title="MORPHEUS Control Plane",
    version="0.2.0",
    description=(
        "Workload-aware data-structure synthesis prototype. Bootstrap costs are predictions, not measurements; "
        "generated artifacts are not called verified until external compilation/correctness gates pass."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

_EVENTS: deque[dict[str, Any]] = deque(maxlen=200)


def _event(kind: str, message: str, **payload: Any) -> None:
    _EVENTS.appendleft(
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "kind": kind,
            "message": message,
            "payload": payload,
        }
    )


def _parse_or_422(raw: str):
    try:
        return parse_workload_text(raw)
    except SpecParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "morpheus-control-plane", "version": "0.2.0"}


@app.get("/api/primitives")
def primitives() -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in PRIMITIVES.values()]


@app.post("/api/validate")
def validate(request: SpecTextRequest) -> dict[str, Any]:
    try:
        spec = _parse_or_422(request.spec_text)
    except HTTPException as exc:
        _event("validation_failed", "Workload validation failed", error=str(exc.detail))
        raise

    digest = semantic_hash(spec)
    _event("validated", "Workload specification validated", spec_hash=digest, name=spec.name)
    return {
        "valid": True,
        "spec_hash": digest,
        "resolved_spec": canonical_dict(spec),
        "evidence_state": "STRUCTURAL_VALIDATION_ONLY",
    }


@app.post("/api/synthesize")
def run_synthesis(request: SpecTextRequest) -> dict[str, Any]:
    try:
        spec = _parse_or_422(request.spec_text)
    except HTTPException as exc:
        _event("synthesis_rejected", "Synthesis rejected during validation", error=str(exc.detail))
        raise

    result = synthesize(spec)
    _event(
        "synthesis_complete",
        "Synthesis search completed",
        spec_hash=result.spec_hash,
        winner=result.winner.id if result.winner else None,
        candidates=len(result.candidates),
        evidence_state=result.evidence_state,
    )
    return result.model_dump(mode="json")


@app.post("/api/artifact/header")
def generated_header(request: SpecTextRequest) -> dict[str, Any]:
    spec = _parse_or_422(request.spec_text)
    result = synthesize(spec)
    if result.winner is None:
        _event("artifact_rejected", "No feasible configuration exists for artifact generation", spec_hash=result.spec_hash)
        raise HTTPException(status_code=409, detail="no feasible configuration satisfies all hard constraints")

    try:
        artifact = generate_verified_header(spec, result.winner)
    except ArtifactCodegenError as exc:
        _event("artifact_unsupported", "Selected configuration is not yet codegen-compatible", error=str(exc))
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    _event(
        "artifact_generated",
        "Standalone C++20 header generated; external compile/correctness verification still required",
        candidate_id=artifact.candidate_id,
        header_name=artifact.header_name,
    )
    return {
        "candidate_id": artifact.candidate_id,
        "header_name": artifact.header_name,
        "source": artifact.header_source,
        "evidence_state": "GENERATED_NOT_EXTERNALLY_VERIFIED",
    }


@app.post("/api/adaptation/decide")
def adaptation(request: AdaptationRequest) -> dict[str, Any]:
    decision = decide_adaptation(
        request.snapshot,
        current_predicted_latency_us=request.current_predicted_latency_us,
        alternative_predicted_latency_us=request.alternative_predicted_latency_us,
        estimated_switching_cost_us=request.estimated_switching_cost_us,
        lambda_factor=request.lambda_factor,
        safety_margin_ratio=request.safety_margin_ratio,
    )
    _event("adaptation_decision", decision.reason, action=decision.action)
    return decision.model_dump(mode="json")


@app.get("/api/events")
def events() -> list[dict[str, Any]]:
    return list(_EVENTS)
