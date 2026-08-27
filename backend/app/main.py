from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .artifact_codegen import ArtifactCodegenError, generate_verified_header
from .calibration import CALIBRATIONS, profile_from_smoke_payload
from .catalog import PRIMITIVES
from .engine import DEFAULT_BEAM_WIDTH, DEFAULT_MAX_CANDIDATES, synthesize
from .models import CalibrationProfile, ObservedWorkloadSnapshot, SearchStrategy
from .parser import SpecParseError, canonical_dict, parse_workload_text, semantic_hash
from .runtime import decide_adaptation


class SpecTextRequest(BaseModel):
    spec_text: str = Field(min_length=1)


class SynthesisRequest(SpecTextRequest):
    strategy: SearchStrategy = SearchStrategy.AUTO
    max_candidates: int = Field(default=DEFAULT_MAX_CANDIDATES, ge=1, le=100_000)
    beam_width: int = Field(default=DEFAULT_BEAM_WIDTH, ge=1, le=4096)


class CalibrationImportRequest(BaseModel):
    payload: dict[str, Any]
    activate: bool = False


class AdaptationRequest(BaseModel):
    snapshot: ObservedWorkloadSnapshot
    current_predicted_latency_us: float = Field(gt=0)
    alternative_predicted_latency_us: float = Field(gt=0)
    estimated_switching_cost_us: float = Field(ge=0)
    lambda_factor: float = Field(default=1.5, gt=0)
    safety_margin_ratio: float = Field(default=0.10, ge=0, le=1)


app = FastAPI(
    title="MORPHEUS Control Plane",
    version="0.3.0",
    description=(
        "Workload-aware data-structure synthesis prototype with explicit search provenance and opt-in calibration. "
        "Predictions, measurements and externally verified artifacts remain separate evidence states."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

_EVENTS: deque[dict[str, Any]] = deque(maxlen=500)


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
    return {"status": "ok", "service": "morpheus-control-plane", "version": "0.3.0"}


@app.get("/api/primitives")
def primitives() -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in PRIMITIVES.values()]


@app.get("/api/capabilities")
def capabilities() -> dict[str, Any]:
    return {
        "mws": "IMPLEMENTED_TESTED",
        "deterministic_search": "IMPLEMENTED_TESTED",
        "beam_search": "IMPLEMENTED",
        "pareto_front": "IMPLEMENTED",
        "calibration_import": "IMPLEMENTED",
        "calibrated_cost_model": "IMPLEMENTED_MODEL_NOT_END_TO_END_MEASURED",
        "artifact_codegen": "IMPLEMENTED_TESTED",
        "runtime_hot_swap": "NOT_IMPLEMENTED",
        "copilot_llm": "NOT_IMPLEMENTED",
    }


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
def run_synthesis(request: SynthesisRequest) -> dict[str, Any]:
    try:
        spec = _parse_or_422(request.spec_text)
    except HTTPException as exc:
        _event("synthesis_rejected", "Synthesis rejected during validation", error=str(exc.detail))
        raise

    result = synthesize(
        spec,
        strategy=request.strategy,
        max_candidates=request.max_candidates,
        beam_width=request.beam_width,
    )
    _event(
        "synthesis_complete",
        "Synthesis search completed",
        spec_hash=result.spec_hash,
        winner=result.winner.id if result.winner else None,
        candidates=len(result.candidates),
        strategy=result.search_summary.strategy.value if result.search_summary else request.strategy.value,
        evidence_state=result.evidence_state,
        calibration_profile=result.active_calibration_profile,
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


@app.get("/api/calibration/profiles")
def calibration_profiles() -> dict[str, Any]:
    return {
        "active_profile": CALIBRATIONS.active_profile_id,
        "profiles": [profile.model_dump(mode="json") for profile in CALIBRATIONS.list_profiles()],
    }


@app.post("/api/calibration/profiles")
def register_calibration(profile: CalibrationProfile) -> dict[str, Any]:
    CALIBRATIONS.register(profile)
    _event(
        "calibration_registered",
        "Calibration profile registered; synthesis behavior is unchanged until activation",
        profile_id=profile.id,
        protocol=profile.protocol,
        evidence_state=profile.evidence_state,
    )
    return {"profile": profile.model_dump(mode="json"), "active": CALIBRATIONS.active_profile_id == profile.id}


@app.post("/api/calibration/import")
def import_calibration(request: CalibrationImportRequest) -> dict[str, Any]:
    try:
        profile = profile_from_smoke_payload(request.payload)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    CALIBRATIONS.register(profile)
    if request.activate:
        CALIBRATIONS.activate(profile.id)
    _event(
        "calibration_imported",
        "Calibration harness payload normalized and registered",
        profile_id=profile.id,
        active=request.activate,
        evidence_state=profile.evidence_state,
    )
    return {"profile": profile.model_dump(mode="json"), "active": CALIBRATIONS.active_profile_id == profile.id}


@app.post("/api/calibration/activate/{profile_id}")
def activate_calibration(profile_id: str) -> dict[str, Any]:
    try:
        profile = CALIBRATIONS.activate(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _event(
        "calibration_activated",
        "Calibration profile activated for supported cost-model operations",
        profile_id=profile.id,
    )
    return {"active_profile": profile.id, "evidence_state": profile.evidence_state}


@app.post("/api/calibration/deactivate")
def deactivate_calibration() -> dict[str, Any]:
    previous = CALIBRATIONS.active_profile_id
    CALIBRATIONS.deactivate()
    _event("calibration_deactivated", "Calibration profile deactivated; bootstrap priors restored", previous=previous)
    return {"active_profile": None}


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
