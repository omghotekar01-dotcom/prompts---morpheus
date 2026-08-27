from __future__ import annotations

from app.adaptation_orchestrator import SafeAdaptationOrchestrator
from app.dataplane import VersionedArtifactRouter
from app.migration import MigrationController
from app.models import ObservedWorkloadSnapshot, QueryKind
from app.runtime import RuntimeController


A = "a" * 64
B = "b" * 64
VERIFY_A = "1" * 64
VERIFY_B = "2" * 64


def _snapshot(sequence: int, point: float, range_scan: float) -> ObservedWorkloadSnapshot:
    return ObservedWorkloadSnapshot(
        operation_mix={QueryKind.POINT_LOOKUP: point, QueryKind.RANGE_SCAN: range_scan},
        expected_future_queries=100_000,
        sequence=sequence,
    )


def _stack() -> tuple[RuntimeController, MigrationController, VersionedArtifactRouter, SafeAdaptationOrchestrator]:
    runtime = RuntimeController()
    migrations = MigrationController()
    router = VersionedArtifactRouter()
    orchestrator = SafeAdaptationOrchestrator(runtime, migrations, router)
    runtime.start(
        "session",
        active_candidate_id="candidate-a",
        baseline=_snapshot(0, 0.9, 0.1),
        drift_threshold=0.2,
        cooldown_windows=0,
    )
    decision, _ = runtime.observe(
        "session",
        snapshot=_snapshot(1, 0.1, 0.9),
        alternative_candidate_id="candidate-b",
        current_predicted_latency_us=10,
        alternative_predicted_latency_us=2,
        estimated_switching_cost_us=1000,
    )
    assert decision.action == "SWITCH_RECOMMENDED"
    router.bootstrap(
        "deployment",
        candidate_id="candidate-a",
        artifact_sha256=A,
        verification_manifest_sha256=VERIFY_A,
    )
    orchestrator.bind_deployment("session", deployment_id="deployment")
    return runtime, migrations, router, orchestrator


def test_verified_migration_can_stage_then_atomically_route_new_local_artifact() -> None:
    runtime, migrations, router, orchestrator = _stack()
    old_reader = router.lease("deployment")
    orchestrator.plan_pending("session", migration_id="migration")
    migrations.shadow_built("migration", artifact_sha256=B)
    migrations.verify(
        "migration",
        compile_verified=True,
        correctness_verified=True,
        verification_manifest_sha256=VERIFY_B,
    )
    staged = orchestrator.stage_verified_migration("migration")
    assert staged["deployment"]["staged"]["candidate_id"] == "candidate-b"

    committed = orchestrator.authorize_commit("session", migration_id="migration")
    assert committed["evidence_state"] == "LOCAL_IN_PROCESS_DATA_PLANE_AND_CONTROL_PLANE_COMMITTED"
    assert committed["runtime"]["active_candidate_id"] == "candidate-b"
    assert committed["data_plane"]["active"]["candidate_id"] == "candidate-b"
    assert router.lease("deployment").version.candidate_id == "candidate-b"
    # Existing readers retain a stable reference to the old version.
    assert old_reader.version.candidate_id == "candidate-a"


def test_orchestrated_rollback_restores_local_route_and_runtime_candidate() -> None:
    runtime, migrations, router, orchestrator = _stack()
    orchestrator.plan_pending("session", migration_id="migration")
    migrations.shadow_built("migration", artifact_sha256=B)
    migrations.verify(
        "migration",
        compile_verified=True,
        correctness_verified=True,
        verification_manifest_sha256=VERIFY_B,
    )
    orchestrator.stage_verified_migration("migration")
    orchestrator.authorize_commit("session", migration_id="migration")

    rolled_back = orchestrator.rollback("session", migration_id="migration", reason="health regression")
    assert rolled_back["evidence_state"] == "LOCAL_IN_PROCESS_DATA_PLANE_AND_CONTROL_PLANE_ROLLED_BACK"
    assert rolled_back["runtime"]["active_candidate_id"] == "candidate-a"
    assert rolled_back["data_plane"]["active"]["candidate_id"] == "candidate-a"
    assert rolled_back["data_plane"]["active"]["generation"] == 3


def test_orchestrated_abort_removes_verified_staged_route() -> None:
    runtime, migrations, router, orchestrator = _stack()
    orchestrator.plan_pending("session", migration_id="migration")
    migrations.shadow_built("migration", artifact_sha256=B)
    migrations.verify(
        "migration",
        compile_verified=True,
        correctness_verified=True,
        verification_manifest_sha256=VERIFY_B,
    )
    orchestrator.stage_verified_migration("migration")
    aborted = orchestrator.abort("session", migration_id="migration", reason="operator cancelled")
    assert aborted["data_plane"]["staged"] is None
    assert router.get("deployment")["active"]["candidate_id"] == "candidate-a"
    assert runtime.get("session")["pending_candidate_id"] is None
