from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .adaptation_orchestrator import SafeAdaptationOrchestrator
from .completion import engineering_completion_report
from .dataplane import DATA_PLANE
from .engine import synthesize
from .generated_migration_bundle import build_generated_migration_bundle, select_distinct_migration_pair
from .generated_migration_evidence import canonical_generated_migration_manifest_bytes
from .generated_migration_verifier import verify_generated_migration_bundle
from .heldout_evaluation import HeldoutCandidateMeasurement, evaluate_heldout_candidate_groups
from .language_layer import answer_with_language_layer
from .migration import MIGRATIONS
from .models import CandidateResult, SynthesisResult
from .parser import SpecParseError, parse_workload_text
from .runtime import RUNTIME
from .storage import STORE
from .workload_ir import canonical_ir_dict, lower_and_hash_workload_ir


router = APIRouter(prefix="/api/v2", tags=["MORPHEUS v2 evidence-safe control plane"])
ADAPTATION_V2 = SafeAdaptationOrchestrator(RUNTIME, MIGRATIONS, DATA_PLANE)


class CopilotLanguageRequest(BaseModel):
    run_id: str = Field(min_length=1, max_length=128)
    question: str = Field(min_length=1, max_length=4000)


class WorkloadIRRequest(BaseModel):
    spec_text: str = Field(min_length=1, max_length=256_000)


class GeneratedMigrationBundleRequest(BaseModel):
    spec_text: str = Field(min_length=1, max_length=256_000)
    source_candidate_id: str | None = Field(default=None, min_length=1, max_length=128)
    target_candidate_id: str | None = Field(default=None, min_length=1, max_length=128)
    record_count: int = Field(default=128, ge=1, le=4096)
    include_sources: bool = True


class GeneratedMigrationVerificationRequest(BaseModel):
    spec_text: str = Field(min_length=1, max_length=256_000)
    source_candidate_id: str | None = Field(default=None, min_length=1, max_length=128)
    target_candidate_id: str | None = Field(default=None, min_length=1, max_length=128)
    record_count: int = Field(default=128, ge=1, le=4096)
    compile_timeout_seconds: int = Field(default=120, ge=1, le=600)
    run_timeout_seconds: int = Field(default=60, ge=1, le=600)


class HeldoutCandidateRequest(BaseModel):
    workload_id: str = Field(min_length=1, max_length=256)
    candidate_id: str = Field(min_length=1, max_length=256)
    predicted: float = Field(ge=0)
    measured: float = Field(ge=0)


class HeldoutEvaluationRequest(BaseModel):
    measurements: list[HeldoutCandidateRequest] = Field(min_length=2, max_length=100_000)
    top_k: int = Field(default=3, ge=1, le=1000)
    bootstrap_rounds: int = Field(default=2000, ge=100, le=100_000)
    bootstrap_seed: int = Field(default=1337, ge=0)


class DataPlaneBootstrapRequest(BaseModel):
    deployment_id: str = Field(min_length=1, max_length=128)
    candidate_id: str = Field(min_length=1, max_length=128)
    artifact_sha256: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    verification_manifest_sha256: str | None = Field(default=None, pattern=r"^[A-Fa-f0-9]{64}$")
    metadata: dict[str, Any] = Field(default_factory=dict)


class DataPlaneBindRequest(BaseModel):
    deployment_id: str = Field(min_length=1, max_length=128)


class DataPlaneActionRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=512)


def capabilities_v2_payload() -> dict[str, str]:
    """Canonical engineering capability ledger for the v0.10 control plane.

    Capability strings intentionally encode scope. In particular, local
    in-process reference activation is separate from native/cross-process live
    hot swap, the optional language layer is separate from evidence authority,
    measured calibration is distinguished from end-to-end candidate proof, and
    prompt-corpus integrity is distinct from software/scientific completion.
    """

    return {
        "mws": "IMPLEMENTED_TESTED",
        "workload_ir": "IMPLEMENTED_DETERMINISTIC_TYPED_HASHED",
        "deterministic_search": "IMPLEMENTED_TESTED",
        "greedy_search": "IMPLEMENTED_TESTED_MYOPIC_BASELINE",
        "beam_search": "IMPLEMENTED_TESTED",
        "pareto_front": "IMPLEMENTED_TESTED",
        "search_quality_oracle_evaluation": "IMPLEMENTED_TESTED_MODEL_ORACLE",
        "heldout_prediction_evaluation": "IMPLEMENTED_TESTED_CALLER_MEASUREMENTS",
        "heldout_grouped_ranking_evaluation": "IMPLEMENTED_TESTED_CALLER_MEASUREMENTS",
        "research_experiment_suite": "IMPLEMENTED_TESTED",
        "feature_policy_registry": "IMPLEMENTED_TESTED_FAIL_CLOSED_PROMOTION",
        "feature_policy_fingerprint": "IMPLEMENTED_TESTED_CANONICAL_SHA256",
        "api_contract_fingerprint": "IMPLEMENTED_TESTED_ROUTE_FINGERPRINT",
        "calibration_import": "IMPLEMENTED_TESTED",
        "calibration_persistence": "IMPLEMENTED_SQLITE_DURABLE",
        "calibrated_cost_model": "IMPLEMENTED_MODEL_NOT_END_TO_END_MEASURED",
        "distribution_bound_calibration": "IMPLEMENTED_TESTED_EXACT_IMPLEMENTATION_OPERATION_SCALE_DISTRIBUTION",
        "distribution_calibration_matrix": "IMPLEMENTED_TESTED_CI_SMOKE_EXPLORATORY_PACKAGE",
        "workload_calibration_coverage": "IMPLEMENTED_TESTED_FAIL_CLOSED_SCALE_DISTRIBUTION",
        "distribution_aware_mutation_cost": "IMPLEMENTED_TESTED_EXACT_OPERATION_DISTRIBUTION",
        "paired_baseline_matrix": "IMPLEMENTED_MEASURED_CI_SMOKE",
        "specialist_baseline_matrix": "IMPLEMENTED_OPTIONAL_ADAPTERS_CI_SMOKE",
        "bplus_tree_primitive": "IMPLEMENTED_TESTED",
        "artifact_codegen": "IMPLEMENTED_TESTED",
        "artifact_compile_gate": "IMPLEMENTED_CROSS_PLATFORM_LOCAL_TOOLCHAIN_NOT_SANDBOXED",
        "artifact_stateful_differential_gate": "IMPLEMENTED_SCHEMA_DERIVED_LOCAL_TOOLCHAIN",
        "generated_migration_bundle": "IMPLEMENTED_TESTED_GENERATED_PROVENANCE_BOUND",
        "generated_migration_execution_gate": "IMPLEMENTED_TESTED_CROSS_PLATFORM_LOCAL_TOOLCHAIN",
        "generated_migration_release_evidence": "IMPLEMENTED_TESTED_FAIL_CLOSED_NARROW_CLAIM",
        "core_sanitizer_gate": "IMPLEMENTED_CI_ASAN_UBSAN",
        "persistent_run_metadata": "IMPLEMENTED_SQLITE",
        "content_addressed_artifacts": "IMPLEMENTED_LOCAL_FILESYSTEM",
        "tamper_evident_evidence_ledger": "IMPLEMENTED_SHA256_HASH_CHAIN",
        "runtime_drift_detection": "IMPLEMENTED_TESTED",
        "runtime_hysteresis_control": "IMPLEMENTED_CONTROL_PLANE",
        "runtime_rollback_control": "IMPLEMENTED_CONTROL_PLANE",
        "runtime_gated_migration": "IMPLEMENTED_CONTROL_PLANE",
        "local_dataplane_swap": "IMPLEMENTED_TESTED_IN_PROCESS",
        "runtime_hot_swap": "NOT_IMPLEMENTED_NATIVE_CROSS_PROCESS",
        "copilot_evidence_mode": "IMPLEMENTED_DETERMINISTIC",
        "copilot_optional_language_layer": "IMPLEMENTED_TOOL_RESTRICTED",
        "copilot_llm": "OPTIONAL_TOOL_RESTRICTED",
        "reproducibility_manifest": "IMPLEMENTED_LOCAL_HASH_MANIFEST",
        "contract_bound_reproducibility": "IMPLEMENTED_TESTED_EXACT_COMMIT_API_FEATURE_POLICY_HASHES",
        "release_claim_gate": "IMPLEMENTED_TESTED_ARTIFACT_BACKED",
        "release_evidence_package": "IMPLEMENTED_TESTED_STRUCTURAL_VALIDATION",
        "distribution_release_provenance": "IMPLEMENTED_TESTED_STRUCTURAL_AND_CROSS_HASH_VALIDATION",
        "prompt_corpus_integrity": "IMPLEMENTED_TESTED_39_CANONICAL_PROMPTS",
        "optional_api_key_and_rate_limit": "IMPLEMENTED_PROCESS_LOCAL",
        "bounded_local_worker": "IMPLEMENTED_TESTED_HOST_PROCESS",
        "windows_python314_ci": "IMPLEMENTED_CI",
        "windows_msvc_cpp20_ci": "IMPLEMENTED_CI",
    }


def _resolve_migration_pair(
    synthesis: SynthesisResult,
    source_candidate_id: str | None,
    target_candidate_id: str | None,
) -> tuple[CandidateResult, CandidateResult]:
    if source_candidate_id is None and target_candidate_id is None:
        return select_distinct_migration_pair(synthesis)

    by_id = {candidate.id: candidate for candidate in synthesis.candidates}
    if synthesis.winner is None:
        raise ValueError("synthesis has no feasible winner")

    if source_candidate_id is None:
        source = synthesis.winner
    else:
        source = by_id.get(source_candidate_id)
        if source is None:
            raise ValueError(f"unknown source candidate id: {source_candidate_id}")
    if not source.feasible:
        raise ValueError("source candidate is not feasible")

    if target_candidate_id is None:
        target = next(
            (candidate for candidate in synthesis.candidates if candidate.feasible and candidate.id != source.id),
            None,
        )
        if target is None:
            raise ValueError("synthesis does not contain a distinct feasible target candidate")
    else:
        target = by_id.get(target_candidate_id)
        if target is None:
            raise ValueError(f"unknown target candidate id: {target_candidate_id}")
    if not target.feasible:
        raise ValueError("target candidate is not feasible")
    if target.id == source.id:
        raise ValueError("source and target candidates must be distinct")
    return source, target


def _build_migration_bundle_from_request(
    request: GeneratedMigrationBundleRequest | GeneratedMigrationVerificationRequest,
):
    spec = parse_workload_text(request.spec_text)
    synthesis = synthesize(spec)
    source, target = _resolve_migration_pair(
        synthesis,
        request.source_candidate_id,
        request.target_candidate_id,
    )
    bundle = build_generated_migration_bundle(
        spec,
        source,
        target,
        record_count=request.record_count,
    )
    return spec, synthesis, source, target, bundle


@router.get("/capabilities")
def capabilities_v2() -> dict[str, str]:
    return capabilities_v2_payload()


@router.get("/completion")
def completion_v2() -> dict[str, Any]:
    return engineering_completion_report(capabilities_v2_payload())


@router.post("/workload/ir")
def workload_ir(request: WorkloadIRRequest) -> dict[str, Any]:
    try:
        spec = parse_workload_text(request.spec_text)
        ir, digest = lower_and_hash_workload_ir(spec)
    except (SpecParseError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "workload_ir_hash": digest,
        "workload_ir": canonical_ir_dict(ir),
        "source_spec_hash": ir.source_spec_hash,
        "evidence_state": "DETERMINISTIC_SEMANTIC_LOWERING",
        "truth_boundary": "This establishes canonical compiler input identity; it is not performance evidence.",
    }


@router.post("/migration/generated/bundle")
def generated_migration_bundle(request: GeneratedMigrationBundleRequest) -> dict[str, Any]:
    """Generate provenance-bound source/target headers plus a native migration harness.

    The endpoint performs synthesis and deterministic source generation only. It
    does not execute a compiler or mutate a live deployment. Compile/run evidence
    remains an explicit downstream verification gate.
    """

    try:
        _spec, synthesis, source, target, bundle = _build_migration_bundle_from_request(request)
    except (SpecParseError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    payload = bundle.as_dict(include_sources=request.include_sources)
    payload["search_evidence_state"] = synthesis.evidence_state
    payload["source_prediction_source"] = source.prediction_source
    payload["target_prediction_source"] = target.prediction_source
    return payload


@router.post("/migration/generated/verify")
def verify_generated_migration(request: GeneratedMigrationVerificationRequest) -> dict[str, Any]:
    """Generate, compile, execute and persist one same-process migration proof.

    Verification uses MORPHEUS-generated C++ in a private temporary workspace,
    with a discovered local compiler, bounded timeouts and no shell. It never
    mutates a registered live deployment. The persisted manifest remains local
    toolchain evidence and does not authorize the broader cross-process hot-swap
    claim.
    """

    try:
        _spec, synthesis, source, target, bundle = _build_migration_bundle_from_request(request)
    except (SpecParseError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    verification = verify_generated_migration_bundle(
        bundle,
        compile_timeout_seconds=request.compile_timeout_seconds,
        run_timeout_seconds=request.run_timeout_seconds,
    )
    spec_hash = synthesis.spec_hash
    source_header_metadata = STORE.store_artifact(
        content=bundle.source_artifact.header_source,
        kind="generated_cpp20_header",
        file_name=bundle.source_artifact.header_name,
        evidence_state="GENERATED_SOURCE_FOR_MIGRATION_VERIFICATION",
        candidate_id=source.id,
        spec_hash=spec_hash,
    )
    target_header_metadata = STORE.store_artifact(
        content=bundle.target_artifact.header_source,
        kind="generated_cpp20_header",
        file_name=bundle.target_artifact.header_name,
        evidence_state="GENERATED_TARGET_FOR_MIGRATION_VERIFICATION",
        candidate_id=target.id,
        spec_hash=spec_hash,
    )
    harness_metadata = STORE.store_artifact(
        content=bundle.harness_source,
        kind="generated_migration_harness",
        file_name=f"migration-{source.id}-to-{target.id}.cpp",
        evidence_state="GENERATED_MIGRATION_HARNESS_SOURCE",
        candidate_id=target.id,
        spec_hash=spec_hash,
    )
    manifest_text = canonical_generated_migration_manifest_bytes(verification).decode("utf-8")
    manifest_metadata = STORE.store_artifact(
        content=manifest_text,
        kind="generated_migration_verification_manifest",
        file_name=f"verify-migration-{source.id}-to-{target.id}.json",
        evidence_state=verification.evidence_state,
        candidate_id=target.id,
        spec_hash=spec_hash,
    )
    return {
        "source_candidate_id": source.id,
        "target_candidate_id": target.id,
        "spec_hash": spec_hash,
        "search_evidence_state": synthesis.evidence_state,
        "source_header_artifact": source_header_metadata,
        "target_header_artifact": target_header_metadata,
        "migration_harness_artifact": harness_metadata,
        "verification_manifest_artifact": manifest_metadata,
        "verification": verification.as_dict(),
        "truth_boundary": (
            "This is persisted same-process generated-migration evidence on one local toolchain. It neither mutates a live "
            "deployment nor establishes concurrent-writer, cross-process/distributed, production-SLA or performance claims."
        ),
    }


@router.post("/research/heldout/evaluate")
def heldout_evaluation(request: HeldoutEvaluationRequest) -> dict[str, Any]:
    try:
        report = evaluate_heldout_candidate_groups(
            (
                HeldoutCandidateMeasurement(
                    workload_id=item.workload_id,
                    candidate_id=item.candidate_id,
                    predicted=item.predicted,
                    measured=item.measured,
                )
                for item in request.measurements
            ),
            top_k=request.top_k,
            bootstrap_rounds=request.bootstrap_rounds,
            bootstrap_seed=request.bootstrap_seed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "report": report.as_dict(),
        "evidence_state": report.evidence_state,
        "truth_boundary": (
            "This endpoint computes ranking/error/regret statistics from supplied held-out measurements; "
            "it does not certify how those measurements were collected."
        ),
    }


@router.post("/copilot/explain")
def copilot_language(request: CopilotLanguageRequest) -> dict[str, Any]:
    run = STORE.get_run(request.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="synthesis run not found")
    try:
        return answer_with_language_layer(run, request.question, provider=None)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/dataplane/deployments")
def dataplane_deployments() -> list[dict[str, Any]]:
    return DATA_PLANE.list()


@router.post("/dataplane/deployments")
def dataplane_bootstrap(request: DataPlaneBootstrapRequest) -> dict[str, Any]:
    try:
        return DATA_PLANE.bootstrap(
            request.deployment_id,
            candidate_id=request.candidate_id,
            artifact_sha256=request.artifact_sha256,
            verification_manifest_sha256=request.verification_manifest_sha256,
            metadata=request.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/dataplane/deployments/{deployment_id}")
def dataplane_detail(deployment_id: str) -> dict[str, Any]:
    try:
        return DATA_PLANE.get(deployment_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/runtime/sessions/{session_id}/dataplane/bind")
def bind_dataplane(session_id: str, request: DataPlaneBindRequest) -> dict[str, Any]:
    try:
        return ADAPTATION_V2.bind_deployment(session_id, deployment_id=request.deployment_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/migrations/{migration_id}/dataplane/stage")
def stage_verified_migration(migration_id: str) -> dict[str, Any]:
    try:
        return ADAPTATION_V2.stage_verified_migration(migration_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/runtime/sessions/{session_id}/migrations/{migration_id}/commit")
def commit_with_dataplane(session_id: str, migration_id: str) -> dict[str, Any]:
    try:
        return ADAPTATION_V2.authorize_commit(session_id, migration_id=migration_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/runtime/sessions/{session_id}/migrations/{migration_id}/rollback")
def rollback_with_dataplane(
    session_id: str,
    migration_id: str,
    request: DataPlaneActionRequest,
) -> dict[str, Any]:
    try:
        return ADAPTATION_V2.rollback(session_id, migration_id=migration_id, reason=request.reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/runtime/sessions/{session_id}/migrations/{migration_id}/abort")
def abort_with_dataplane(
    session_id: str,
    migration_id: str,
    request: DataPlaneActionRequest,
) -> dict[str, Any]:
    try:
        return ADAPTATION_V2.abort(session_id, migration_id=migration_id, reason=request.reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
