from __future__ import annotations

import json
from collections import deque
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .adaptation_orchestrator import SafeAdaptationOrchestrator
from .artifact_codegen import ArtifactCodegenError, generate_verified_header
from .behavior_verifier import verify_generated_artifact_behavior
from .calibration import CALIBRATIONS, profile_from_smoke_payload
from .catalog import PRIMITIVES
from .copilot import answer_from_run
from .engine import DEFAULT_BEAM_WIDTH, DEFAULT_MAX_CANDIDATES, synthesize
from .migration import MIGRATIONS
from .models import CalibrationProfile, ObservedWorkloadSnapshot, SearchStrategy
from .parser import SpecParseError, canonical_dict, parse_workload_text, semantic_hash
from .research import PredictionPoint, evaluate_predictions
from .runtime import RUNTIME, decide_adaptation
from .search_quality import compare_beam_to_exhaustive
from .security import SecurityPolicyMiddleware
from .storage import STORE
from .toolchain import system_diagnostics
from .verifier import verify_generated_header_compile


class SpecTextRequest(BaseModel):
    spec_text: str = Field(min_length=1)


class SynthesisRequest(SpecTextRequest):
    strategy: SearchStrategy = SearchStrategy.AUTO
    max_candidates: int = Field(default=DEFAULT_MAX_CANDIDATES, ge=1, le=100_000)
    beam_width: int = Field(default=DEFAULT_BEAM_WIDTH, ge=1, le=4096)


class CalibrationImportRequest(BaseModel):
    payload: dict[str, Any]
    activate: bool = False


class CopilotRequest(BaseModel):
    run_id: str = Field(min_length=1, max_length=128)
    question: str = Field(min_length=1, max_length=4000)


class AdaptationRequest(BaseModel):
    snapshot: ObservedWorkloadSnapshot
    current_predicted_latency_us: float = Field(gt=0)
    alternative_predicted_latency_us: float = Field(gt=0)
    estimated_switching_cost_us: float = Field(ge=0)
    lambda_factor: float = Field(default=1.5, gt=0)
    safety_margin_ratio: float = Field(default=0.10, ge=0, le=1)


class RuntimeSessionStartRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    active_candidate_id: str = Field(min_length=1, max_length=128)
    baseline: ObservedWorkloadSnapshot
    drift_threshold: float = Field(default=0.18, ge=0, le=1)
    cooldown_windows: int = Field(default=3, ge=0, le=10_000)


class RuntimeObserveRequest(BaseModel):
    snapshot: ObservedWorkloadSnapshot
    alternative_candidate_id: str = Field(min_length=1, max_length=128)
    current_predicted_latency_us: float = Field(gt=0)
    alternative_predicted_latency_us: float = Field(gt=0)
    estimated_switching_cost_us: float = Field(ge=0)
    lambda_factor: float = Field(default=1.5, gt=0)
    safety_margin_ratio: float = Field(default=0.10, ge=0, le=1)


class RuntimeConfirmRequest(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=128)


class RuntimeAbortRequest(BaseModel):
    reason: str = Field(default="operator_or_verification_abort", min_length=1, max_length=512)


class RuntimeRollbackRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=512)


class MigrationPlanRequest(BaseModel):
    migration_id: str = Field(min_length=1, max_length=128)


class MigrationShadowRequest(BaseModel):
    artifact_sha256: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")


class MigrationVerifyRequest(BaseModel):
    compile_verified: bool
    correctness_verified: bool
    verification_manifest_sha256: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")


class MigrationActionRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=512)


class PredictionPointRequest(BaseModel):
    label: str = Field(min_length=1, max_length=256)
    predicted: float = Field(ge=0)
    measured: float = Field(ge=0)


class PredictionEvaluationRequest(BaseModel):
    metric: str = Field(default="unspecified_cost", min_length=1, max_length=128)
    points: list[PredictionPointRequest] = Field(min_length=2, max_length=10_000)


class SearchQualityRequest(SpecTextRequest):
    beam_width: int = Field(default=DEFAULT_BEAM_WIDTH, ge=1, le=4096)
    exhaustive_limit: int = Field(default=100_000, ge=1, le=1_000_000)


app = FastAPI(
    title="MORPHEUS Control Plane",
    version="0.9.0",
    description=(
        "Workload-aware data-structure synthesis prototype with explicit search provenance, durable calibration, "
        "content-addressed artifacts, tamper-evident experiment evidence, cross-platform C++ verification, "
        "stateful differential correctness gates, deterministic evidence Copilot, research evaluators, and a gated "
        "runtime migration control plane. Predictions, measurements, recommendations, verification, migration "
        "authorization and live data-plane state remain distinct evidence classes."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Morpheus-Key"],
)
app.add_middleware(SecurityPolicyMiddleware)

_EVENTS: deque[dict[str, Any]] = deque(maxlen=500)
ADAPTATION = SafeAdaptationOrchestrator(RUNTIME, MIGRATIONS)


def _event(kind: str, message: str, **payload: Any) -> None:
    item = {
        "timestamp": datetime.now(UTC).isoformat(),
        "kind": kind,
        "message": message,
        "payload": payload,
    }
    _EVENTS.appendleft(item)
    STORE.record_event(kind, message, payload)


def _parse_or_422(raw: str):
    try:
        return parse_workload_text(raw)
    except SpecParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _runtime_value_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


def _generated_artifact_or_error(raw_spec: str):
    spec = _parse_or_422(raw_spec)
    result = synthesize(spec)
    if result.winner is None:
        raise HTTPException(status_code=409, detail="no feasible configuration satisfies all hard constraints")
    try:
        artifact = generate_verified_header(spec, result.winner)
    except ArtifactCodegenError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return spec, result, artifact


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "morpheus-control-plane", "version": "0.9.0"}


@app.get("/api/system/diagnostics")
def diagnostics() -> dict[str, object]:
    return system_diagnostics()


@app.get("/api/primitives")
def primitives() -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in PRIMITIVES.values()]


@app.get("/api/capabilities")
def capabilities() -> dict[str, Any]:
    return {
        "mws": "IMPLEMENTED_TESTED",
        "deterministic_search": "IMPLEMENTED_TESTED",
        "beam_search": "IMPLEMENTED_TESTED",
        "pareto_front": "IMPLEMENTED_TESTED",
        "search_quality_oracle_evaluation": "IMPLEMENTED_TESTED_MODEL_ORACLE",
        "heldout_prediction_evaluation": "IMPLEMENTED_TESTED_CALLER_MEASUREMENTS",
        "calibration_import": "IMPLEMENTED_TESTED",
        "calibration_persistence": "IMPLEMENTED_SQLITE_DURABLE",
        "calibrated_cost_model": "IMPLEMENTED_MODEL_NOT_END_TO_END_MEASURED",
        "artifact_codegen": "IMPLEMENTED_TESTED",
        "artifact_compile_gate": "IMPLEMENTED_CROSS_PLATFORM_LOCAL_TOOLCHAIN_NOT_SANDBOXED",
        "artifact_stateful_differential_gate": "IMPLEMENTED_SCHEMA_DERIVED_LOCAL_TOOLCHAIN",
        "core_sanitizer_gate": "IMPLEMENTED_CI_ASAN_UBSAN",
        "persistent_run_metadata": "IMPLEMENTED_SQLITE",
        "content_addressed_artifacts": "IMPLEMENTED_LOCAL_FILESYSTEM",
        "tamper_evident_evidence_ledger": "IMPLEMENTED_SHA256_HASH_CHAIN",
        "runtime_drift_detection": "IMPLEMENTED_TESTED",
        "runtime_hysteresis_control": "IMPLEMENTED_CONTROL_PLANE_ONLY",
        "runtime_rollback_control": "IMPLEMENTED_CONTROL_PLANE_ONLY",
        "runtime_gated_migration": "IMPLEMENTED_CONTROL_PLANE_ONLY",
        "runtime_hot_swap": "NOT_IMPLEMENTED",
        "copilot_evidence_mode": "IMPLEMENTED_DETERMINISTIC",
        "copilot_llm": "NOT_IMPLEMENTED",
        "reproducibility_manifest": "IMPLEMENTED_LOCAL_HASH_MANIFEST",
        "optional_api_key_and_rate_limit": "IMPLEMENTED_PROCESS_LOCAL",
        "windows_python314_ci": "IMPLEMENTED_CI",
        "windows_msvc_cpp20_ci": "IMPLEMENTED_CI",
    }


@app.get("/api/state/summary")
def state_summary() -> dict[str, Any]:
    return STORE.summary()


@app.get("/api/evidence")
def evidence(limit: int = 200) -> list[dict[str, Any]]:
    return STORE.recent_evidence(limit=limit)


@app.get("/api/evidence/verify")
def verify_evidence() -> dict[str, Any]:
    return STORE.verify_evidence_ledger()


@app.get("/api/workloads")
def workloads(limit: int = 100) -> list[dict[str, Any]]:
    return STORE.list_workloads(limit=limit)


@app.get("/api/runs")
def runs(limit: int = 50) -> list[dict[str, Any]]:
    return STORE.list_runs(limit=limit)


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str) -> dict[str, Any]:
    run = STORE.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="synthesis run not found")
    return run


@app.get("/api/artifacts/{sha256}")
def artifact_detail(sha256: str) -> dict[str, Any]:
    artifact = STORE.read_artifact(sha256)
    if artifact is None:
        raise HTTPException(status_code=404, detail="artifact not found")
    metadata, content = artifact
    return {"metadata": metadata, "content": content}


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
    run_id = STORE.save_synthesis(spec, request.spec_text, result)
    _event(
        "synthesis_complete",
        "Synthesis search completed and experiment metadata persisted",
        run_id=run_id,
        spec_hash=result.spec_hash,
        winner=result.winner.id if result.winner else None,
        candidates=len(result.candidates),
        strategy=result.search_summary.strategy.value if result.search_summary else request.strategy.value,
        evidence_state=result.evidence_state,
        calibration_profile=result.active_calibration_profile,
    )
    payload = result.model_dump(mode="json")
    payload["run_id"] = run_id
    return payload


@app.post("/api/artifact/header")
def generated_header(request: SpecTextRequest) -> dict[str, Any]:
    try:
        _spec, result, artifact = _generated_artifact_or_error(request.spec_text)
    except HTTPException as exc:
        _event("artifact_rejected", "Artifact generation rejected", error=str(exc.detail))
        raise

    metadata = STORE.store_artifact(
        content=artifact.header_source,
        kind="generated_cpp20_header",
        file_name=artifact.header_name,
        evidence_state="GENERATED_NOT_EXTERNALLY_VERIFIED",
        candidate_id=artifact.candidate_id,
        spec_hash=result.spec_hash,
    )
    _event(
        "artifact_generated",
        "Standalone C++20 header generated and stored by content hash; external verification still required",
        candidate_id=artifact.candidate_id,
        header_name=artifact.header_name,
        sha256=metadata.get("sha256"),
    )
    return {
        "candidate_id": artifact.candidate_id,
        "header_name": artifact.header_name,
        "source": artifact.header_source,
        "sha256": metadata.get("sha256"),
        "artifact_metadata": metadata,
        "evidence_state": "GENERATED_NOT_EXTERNALLY_VERIFIED",
    }


@app.post("/api/artifact/verify")
def verify_artifact(request: SpecTextRequest) -> dict[str, Any]:
    try:
        _spec, result, artifact = _generated_artifact_or_error(request.spec_text)
    except HTTPException as exc:
        _event("artifact_verification_rejected", "Artifact verification rejected before compile gate", error=str(exc.detail))
        raise

    header_metadata = STORE.store_artifact(
        content=artifact.header_source,
        kind="generated_cpp20_header",
        file_name=artifact.header_name,
        evidence_state="GENERATED_NOT_EXTERNALLY_VERIFIED",
        candidate_id=artifact.candidate_id,
        spec_hash=result.spec_hash,
    )
    verification = verify_generated_header_compile(artifact)
    verification_payload = verification.as_dict()
    manifest_metadata = STORE.store_artifact(
        content=json.dumps(verification_payload, sort_keys=True, indent=2),
        kind="compile_verification_manifest",
        file_name=f"verify-{artifact.candidate_id}.json",
        evidence_state=verification.evidence_state,
        candidate_id=artifact.candidate_id,
        spec_hash=result.spec_hash,
    )
    _event(
        "artifact_compile_gate",
        "Generated artifact compile gate completed",
        candidate_id=artifact.candidate_id,
        success=verification.success,
        evidence_state=verification.evidence_state,
        header_sha256=header_metadata.get("sha256"),
        manifest_sha256=manifest_metadata.get("sha256"),
    )
    return {
        "candidate_id": artifact.candidate_id,
        "spec_hash": result.spec_hash,
        "header_artifact": header_metadata,
        "verification_manifest": manifest_metadata,
        "verification": verification_payload,
    }


@app.post("/api/artifact/verify/full")
def verify_artifact_full(request: SpecTextRequest) -> dict[str, Any]:
    try:
        spec, result, artifact = _generated_artifact_or_error(request.spec_text)
    except HTTPException as exc:
        _event("artifact_full_verification_rejected", "Artifact full verification rejected before gates", error=str(exc.detail))
        raise

    header_metadata = STORE.store_artifact(
        content=artifact.header_source,
        kind="generated_cpp20_header",
        file_name=artifact.header_name,
        evidence_state="GENERATED_NOT_EXTERNALLY_VERIFIED",
        candidate_id=artifact.candidate_id,
        spec_hash=result.spec_hash,
    )
    compile_gate = verify_generated_header_compile(artifact)
    behavior_gate = verify_generated_artifact_behavior(spec, result.winner, artifact)
    success = compile_gate.success and behavior_gate.success
    evidence_state = "FULL_LOCAL_ARTIFACT_GATE_PASSED" if success else "FULL_LOCAL_ARTIFACT_GATE_FAILED"
    manifest = {
        "schema": "morpheus-artifact-verification-v2",
        "candidate_id": artifact.candidate_id,
        "spec_hash": result.spec_hash,
        "header_sha256": header_metadata.get("sha256"),
        "success": success,
        "evidence_state": evidence_state,
        "compile_gate": compile_gate.as_dict(),
        "behavior_gate": behavior_gate.as_dict(),
        "truth_boundaries": [
            "Passing gates establish local toolchain acceptance and deterministic stateful semantic agreement for generated routes.",
            "They do not establish concurrency safety, production isolation, deployed latency, or benchmark superiority.",
        ],
    }
    manifest_metadata = STORE.store_artifact(
        content=json.dumps(manifest, sort_keys=True, indent=2),
        kind="full_artifact_verification_manifest",
        file_name=f"verify-full-{artifact.candidate_id}.json",
        evidence_state=evidence_state,
        candidate_id=artifact.candidate_id,
        spec_hash=result.spec_hash,
    )
    _event(
        "artifact_full_verification_gate",
        "Compile and schema-derived stateful differential gates completed",
        candidate_id=artifact.candidate_id,
        success=success,
        evidence_state=evidence_state,
        header_sha256=header_metadata.get("sha256"),
        manifest_sha256=manifest_metadata.get("sha256"),
        behavioral_checks=behavior_gate.checks,
    )
    return {
        "candidate_id": artifact.candidate_id,
        "spec_hash": result.spec_hash,
        "header_artifact": header_metadata,
        "verification_manifest": manifest_metadata,
        "verification": manifest,
    }


@app.post("/api/copilot/explain")
def copilot_explain(request: CopilotRequest) -> dict[str, Any]:
    run = STORE.get_run(request.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="synthesis run not found")
    try:
        response = answer_from_run(run, request.question)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _event(
        "copilot_explanation",
        "Deterministic evidence-grounded explanation produced",
        run_id=request.run_id,
        mode=response.mode,
        evidence_refs=response.evidence_refs,
    )
    return response.as_dict()


@app.get("/api/calibration/profiles")
def calibration_profiles() -> dict[str, Any]:
    return {
        "active_profile": CALIBRATIONS.active_profile_id,
        "profiles": [profile.model_dump(mode="json") for profile in CALIBRATIONS.list_profiles()],
        "persistence": "SQLITE_DURABLE",
    }


@app.post("/api/calibration/profiles")
def register_calibration(profile: CalibrationProfile) -> dict[str, Any]:
    CALIBRATIONS.register(profile)
    _event(
        "calibration_registered",
        "Calibration profile registered durably; synthesis behavior is unchanged until activation",
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
        "Calibration harness payload normalized and durably registered",
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
        "Calibration profile durably activated for supported cost-model operations",
        profile_id=profile.id,
    )
    return {"active_profile": profile.id, "evidence_state": profile.evidence_state}


@app.post("/api/calibration/deactivate")
def deactivate_calibration() -> dict[str, Any]:
    previous = CALIBRATIONS.active_profile_id
    CALIBRATIONS.deactivate()
    _event("calibration_deactivated", "Calibration profile durably deactivated; bootstrap priors restored", previous=previous)
    return {"active_profile": None}


@app.post("/api/research/predictions/evaluate")
def research_prediction_evaluation(request: PredictionEvaluationRequest) -> dict[str, Any]:
    try:
        evaluation = evaluate_predictions(
            PredictionPoint(item.label, item.predicted, item.measured) for item in request.points
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    payload = evaluation.as_dict()
    _event(
        "research_prediction_evaluation",
        "Held-out prediction evaluation computed from caller-supplied measurements",
        metric=request.metric,
        sample_count=evaluation.sample_count,
        top1_regret_abs=evaluation.top1_regret_abs,
        evidence_state=evaluation.evidence_state,
    )
    return {
        "metric": request.metric,
        "evaluation": payload,
        "truth_note": "The endpoint evaluates supplied measurements; it does not establish how they were collected.",
    }


@app.post("/api/research/search/compare")
def research_search_quality(request: SearchQualityRequest) -> dict[str, Any]:
    spec = _parse_or_422(request.spec_text)
    try:
        report = compare_beam_to_exhaustive(
            spec,
            beam_width=request.beam_width,
            exhaustive_limit=request.exhaustive_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    payload = report.as_dict()
    _event(
        "research_search_quality",
        "Beam search compared with bounded exhaustive model oracle",
        spec_hash=semantic_hash(spec),
        beam_width=request.beam_width,
        absolute_score_regret=report.absolute_score_regret,
        search_reduction_ratio=report.search_reduction_ratio,
    )
    return {
        "spec_hash": semantic_hash(spec),
        "report": payload,
        "truth_note": "This measures heuristic fidelity to MORPHEUS's model oracle, not real-hardware accuracy.",
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


@app.get("/api/runtime/sessions")
def runtime_sessions() -> list[dict[str, Any]]:
    return RUNTIME.list_sessions()


@app.post("/api/runtime/sessions")
def start_runtime_session(request: RuntimeSessionStartRequest) -> dict[str, Any]:
    try:
        session = RUNTIME.start(
            request.session_id,
            active_candidate_id=request.active_candidate_id,
            baseline=request.baseline,
            drift_threshold=request.drift_threshold,
            cooldown_windows=request.cooldown_windows,
        )
    except ValueError as exc:
        raise _runtime_value_error(exc) from exc
    _event(
        "runtime_session_started",
        "Runtime adaptation session started",
        session_id=request.session_id,
        active_candidate_id=request.active_candidate_id,
    )
    return session


@app.get("/api/runtime/sessions/{session_id}")
def runtime_session(session_id: str) -> dict[str, Any]:
    try:
        return RUNTIME.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/runtime/sessions/{session_id}/observe")
def runtime_observe(session_id: str, request: RuntimeObserveRequest) -> dict[str, Any]:
    try:
        decision, session = RUNTIME.observe(
            session_id,
            snapshot=request.snapshot,
            alternative_candidate_id=request.alternative_candidate_id,
            current_predicted_latency_us=request.current_predicted_latency_us,
            alternative_predicted_latency_us=request.alternative_predicted_latency_us,
            estimated_switching_cost_us=request.estimated_switching_cost_us,
            lambda_factor=request.lambda_factor,
            safety_margin_ratio=request.safety_margin_ratio,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise _runtime_value_error(exc) from exc

    _event(
        "runtime_observation",
        decision.reason,
        session_id=session_id,
        action=decision.action,
        pending_candidate_id=session["pending_candidate_id"],
    )
    return {"decision": decision.model_dump(mode="json"), "session": session}


@app.post("/api/runtime/sessions/{session_id}/confirm")
def runtime_confirm(session_id: str, request: RuntimeConfirmRequest) -> dict[str, Any]:
    try:
        session = RUNTIME.confirm(session_id, candidate_id=request.candidate_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise _runtime_value_error(exc) from exc
    _event(
        "runtime_switch_confirmed",
        "Control-plane active candidate changed after explicit confirmation",
        session_id=session_id,
        active_candidate_id=request.candidate_id,
        evidence_state="CONTROL_PLANE_STATE_CHANGE_ONLY",
    )
    return session


@app.post("/api/runtime/sessions/{session_id}/rollback")
def runtime_rollback(session_id: str, request: RuntimeRollbackRequest) -> dict[str, Any]:
    try:
        session = RUNTIME.rollback_last_switch(session_id, reason=request.reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise _runtime_value_error(exc) from exc
    _event(
        "runtime_switch_rolled_back",
        "Previous control-plane candidate restored after rollback authorization",
        session_id=session_id,
        active_candidate_id=session["active_candidate_id"],
        reason=request.reason,
        evidence_state="CONTROL_PLANE_ROLLBACK_ONLY",
    )
    return session


@app.post("/api/runtime/sessions/{session_id}/abort")
def runtime_abort(session_id: str, request: RuntimeAbortRequest) -> dict[str, Any]:
    try:
        session = RUNTIME.abort_pending(session_id, reason=request.reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _event(
        "runtime_switch_aborted",
        "Pending adaptation recommendation cleared",
        session_id=session_id,
        reason=request.reason,
    )
    return session


@app.get("/api/migrations")
def migrations() -> list[dict[str, Any]]:
    return MIGRATIONS.list()


@app.get("/api/migrations/{migration_id}")
def migration_detail(migration_id: str) -> dict[str, Any]:
    try:
        return MIGRATIONS.get(migration_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/runtime/sessions/{session_id}/migrations/plan")
def migration_plan(session_id: str, request: MigrationPlanRequest) -> dict[str, Any]:
    try:
        migration = ADAPTATION.plan_pending(session_id, migration_id=request.migration_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise _runtime_value_error(exc) from exc
    _event(
        "migration_planned",
        "Pending runtime recommendation bound to gated migration plan",
        session_id=session_id,
        migration_id=request.migration_id,
        from_candidate_id=migration["from_candidate_id"],
        to_candidate_id=migration["to_candidate_id"],
    )
    return migration


@app.post("/api/migrations/{migration_id}/shadow")
def migration_shadow(migration_id: str, request: MigrationShadowRequest) -> dict[str, Any]:
    try:
        migration = MIGRATIONS.shadow_built(migration_id, artifact_sha256=request.artifact_sha256)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise _runtime_value_error(exc) from exc
    _event(
        "migration_shadow_built",
        "Shadow artifact recorded for migration; verification still required",
        migration_id=migration_id,
        artifact_sha256=migration["artifact_sha256"],
    )
    return migration


@app.post("/api/migrations/{migration_id}/verify")
def migration_verify(migration_id: str, request: MigrationVerifyRequest) -> dict[str, Any]:
    try:
        migration = MIGRATIONS.verify(
            migration_id,
            compile_verified=request.compile_verified,
            correctness_verified=request.correctness_verified,
            verification_manifest_sha256=request.verification_manifest_sha256,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise _runtime_value_error(exc) from exc
    _event(
        "migration_verification_recorded",
        "Migration verification gates recorded",
        migration_id=migration_id,
        compile_verified=request.compile_verified,
        correctness_verified=request.correctness_verified,
        state=migration["state"],
    )
    return migration


@app.post("/api/runtime/sessions/{session_id}/migrations/{migration_id}/commit")
def migration_commit(session_id: str, migration_id: str) -> dict[str, Any]:
    try:
        state = ADAPTATION.authorize_commit(session_id, migration_id=migration_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise _runtime_value_error(exc) from exc
    _event(
        "migration_commit_authorized",
        "Verified migration and runtime control-plane switch committed together",
        session_id=session_id,
        migration_id=migration_id,
        active_candidate_id=state["runtime"]["active_candidate_id"],
        evidence_state=state["evidence_state"],
    )
    return state


@app.post("/api/runtime/sessions/{session_id}/migrations/{migration_id}/rollback")
def migration_rollback(session_id: str, migration_id: str, request: MigrationActionRequest) -> dict[str, Any]:
    try:
        state = ADAPTATION.rollback(session_id, migration_id=migration_id, reason=request.reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise _runtime_value_error(exc) from exc
    _event(
        "migration_rollback_authorized",
        "Migration and runtime control-plane state rolled back together",
        session_id=session_id,
        migration_id=migration_id,
        active_candidate_id=state["runtime"]["active_candidate_id"],
        reason=request.reason,
    )
    return state


@app.post("/api/runtime/sessions/{session_id}/migrations/{migration_id}/abort")
def migration_abort(session_id: str, migration_id: str, request: MigrationActionRequest) -> dict[str, Any]:
    try:
        state = ADAPTATION.abort(session_id, migration_id=migration_id, reason=request.reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise _runtime_value_error(exc) from exc
    _event(
        "migration_aborted",
        "Migration and pending runtime recommendation aborted together",
        session_id=session_id,
        migration_id=migration_id,
        reason=request.reason,
    )
    return state


@app.get("/api/events")
def events(limit: int = 200) -> list[dict[str, Any]]:
    return STORE.recent_events(limit=limit)
