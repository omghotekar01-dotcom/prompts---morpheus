from __future__ import annotations

import pytest

from app.adaptation_orchestrator import SafeAdaptationOrchestrator
from app.dataplane import VersionedArtifactRouter
from app.migration import MigrationController, MigrationState
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


class FailAfterRuntimeConfirm(RuntimeController):
    def confirm(self, session_id: str, *, candidate_id: str):  # type: ignore[override]
        super().confirm(session_id, candidate_id=candidate_id)
        raise RuntimeError("injected failure after runtime confirmation")


class FailAfterMigrationCommit(MigrationController):
    def commit(self, migration_id: str):  # type: ignore[override]
        super().commit(migration_id)
        raise RuntimeError("injected failure after migration commit")


def _stack(
    *,
    runtime: RuntimeController | None = None,
    migrations: MigrationController | None = None,
) -> tuple[RuntimeController, MigrationController, VersionedArtifactRouter, SafeAdaptationOrchestrator]:
    runtime = runtime or RuntimeController()
    migrations = migrations or MigrationController()
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


def _prepare_verified(orchestrator: SafeAdaptationOrchestrator, migrations: MigrationController) -> None:
    orchestrator.plan_pending("session", migration_id="migration")
    migrations.shadow_built("migration", artifact_sha256=B)
    migrations.verify(
        "migration",
        compile_verified=True,
        correctness_verified=True,
        verification_manifest_sha256=VERIFY_B,
    )
    orchestrator.stage_verified_migration("migration")


def test_verified_migration_can_stage_then_atomically_route_new_local_artifact() -> None:
    runtime, migrations, router, orchestrator = _stack()
    old_reader = router.lease("deployment")
    _prepare_verified(orchestrator, migrations)

    committed = orchestrator.authorize_commit("session", migration_id="migration")
    assert committed["evidence_state"] == "LOCAL_IN_PROCESS_DATA_PLANE_AND_CONTROL_PLANE_COMMITTED"
    assert committed["runtime"]["active_candidate_id"] == "candidate-b"
    assert committed["data_plane"]["active"]["candidate_id"] == "candidate-b"
    assert committed["migration"]["state"] == MigrationState.COMMITTED.value
    assert router.lease("deployment").version.candidate_id == "candidate-b"
    # Existing readers retain a stable reference to the old version.
    assert old_reader.version.candidate_id == "candidate-a"


def test_orchestrated_rollback_restores_local_route_and_runtime_candidate() -> None:
    runtime, migrations, router, orchestrator = _stack()
    _prepare_verified(orchestrator, migrations)
    orchestrator.authorize_commit("session", migration_id="migration")

    rolled_back = orchestrator.rollback("session", migration_id="migration", reason="health regression")
    assert rolled_back["evidence_state"] == "LOCAL_IN_PROCESS_DATA_PLANE_AND_CONTROL_PLANE_ROLLED_BACK"
    assert rolled_back["runtime"]["active_candidate_id"] == "candidate-a"
    assert rolled_back["data_plane"]["active"]["candidate_id"] == "candidate-a"
    assert rolled_back["data_plane"]["active"]["generation"] == 3
    assert rolled_back["migration"]["state"] == MigrationState.ROLLED_BACK.value


def test_orchestrated_abort_removes_verified_staged_route() -> None:
    runtime, migrations, router, orchestrator = _stack()
    _prepare_verified(orchestrator, migrations)
    aborted = orchestrator.abort("session", migration_id="migration", reason="operator cancelled")
    assert aborted["data_plane"]["staged"] is None
    assert router.get("deployment")["active"]["candidate_id"] == "candidate-a"
    assert runtime.get("session")["pending_candidate_id"] is None


def test_failure_after_runtime_confirm_is_compensated_without_false_commit() -> None:
    runtime = FailAfterRuntimeConfirm()
    runtime, migrations, router, orchestrator = _stack(runtime=runtime)
    _prepare_verified(orchestrator, migrations)

    with pytest.raises(RuntimeError, match="injected failure after runtime confirmation"):
        orchestrator.authorize_commit("session", migration_id="migration")

    assert runtime.get("session")["active_candidate_id"] == "candidate-a"
    assert runtime.get("session")["rollback_available"] is False
    assert router.get("deployment")["active"]["candidate_id"] == "candidate-a"
    assert migrations.get("migration")["state"] == MigrationState.VERIFIED.value


def test_failure_after_migration_commit_compensates_all_already_changed_controllers() -> None:
    migrations = FailAfterMigrationCommit()
    runtime, migrations, router, orchestrator = _stack(migrations=migrations)
    _prepare_verified(orchestrator, migrations)

    with pytest.raises(RuntimeError, match="injected failure after migration commit"):
        orchestrator.authorize_commit("session", migration_id="migration")

    assert runtime.get("session")["active_candidate_id"] == "candidate-a"
    assert runtime.get("session")["rollback_available"] is False
    assert router.get("deployment")["active"]["candidate_id"] == "candidate-a"
    # The injected failure happened after COMMITTED; compensation records a real rollback.
    assert migrations.get("migration")["state"] == MigrationState.ROLLED_BACK.value


def test_wrong_session_rollback_is_rejected_before_any_state_mutation() -> None:
    runtime, migrations, router, orchestrator = _stack()
    _prepare_verified(orchestrator, migrations)
    orchestrator.authorize_commit("session", migration_id="migration")
    before_runtime = runtime.get("session")
    before_deployment = router.get("deployment")
    before_migration = migrations.get("migration")

    with pytest.raises(ValueError, match="does not belong"):
        orchestrator.rollback("different-session", migration_id="migration", reason="invalid caller")

    assert runtime.get("session")["active_candidate_id"] == before_runtime["active_candidate_id"]
    assert router.get("deployment")["active"] == before_deployment["active"]
    assert migrations.get("migration")["state"] == before_migration["state"]


def test_second_rollback_fails_closed_without_extra_generation_or_state_change() -> None:
    runtime, migrations, router, orchestrator = _stack()
    _prepare_verified(orchestrator, migrations)
    orchestrator.authorize_commit("session", migration_id="migration")
    orchestrator.rollback("session", migration_id="migration", reason="first rollback")
    before_runtime = runtime.get("session")
    before_deployment = router.get("deployment")

    with pytest.raises(ValueError, match="COMMITTED"):
        orchestrator.rollback("session", migration_id="migration", reason="duplicate rollback")

    assert runtime.get("session")["active_candidate_id"] == before_runtime["active_candidate_id"]
    assert router.get("deployment")["active"] == before_deployment["active"]
    assert migrations.get("migration")["state"] == MigrationState.ROLLED_BACK.value
