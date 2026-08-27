from __future__ import annotations

import pytest

from app.adaptation_orchestrator import SafeAdaptationOrchestrator
from app.migration import MigrationController
from app.models import ObservedWorkloadSnapshot, QueryKind
from app.runtime import RuntimeController


ARTIFACT = "a" * 64
MANIFEST = "b" * 64


def _snapshot(sequence: int, point: float, range_scan: float) -> ObservedWorkloadSnapshot:
    return ObservedWorkloadSnapshot(
        operation_mix={QueryKind.POINT_LOOKUP: point, QueryKind.RANGE_SCAN: range_scan},
        expected_future_queries=100_000,
        sequence=sequence,
    )


def _recommended_stack() -> tuple[RuntimeController, MigrationController, SafeAdaptationOrchestrator]:
    runtime = RuntimeController()
    migrations = MigrationController()
    orchestrator = SafeAdaptationOrchestrator(runtime, migrations)
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
    return runtime, migrations, orchestrator


def test_orchestrator_requires_verified_migration_before_runtime_confirmation() -> None:
    runtime, migrations, orchestrator = _recommended_stack()
    orchestrator.plan_pending("session", migration_id="migration")

    with pytest.raises(ValueError, match="VERIFIED"):
        orchestrator.authorize_commit("session", migration_id="migration")
    assert runtime.get("session")["active_candidate_id"] == "candidate-a"

    migrations.shadow_built("migration", artifact_sha256=ARTIFACT)
    migrations.verify(
        "migration",
        compile_verified=True,
        correctness_verified=True,
        verification_manifest_sha256=MANIFEST,
    )
    committed = orchestrator.authorize_commit("session", migration_id="migration")
    assert committed["migration"]["state"] == "COMMITTED"
    assert committed["runtime"]["active_candidate_id"] == "candidate-b"
    assert committed["runtime"]["rollback_available"] is True


def test_orchestrator_rollback_restores_runtime_and_migration_state() -> None:
    runtime, migrations, orchestrator = _recommended_stack()
    orchestrator.plan_pending("session", migration_id="migration")
    migrations.shadow_built("migration", artifact_sha256=ARTIFACT)
    migrations.verify(
        "migration",
        compile_verified=True,
        correctness_verified=True,
        verification_manifest_sha256=MANIFEST,
    )
    orchestrator.authorize_commit("session", migration_id="migration")

    rolled_back = orchestrator.rollback(
        "session",
        migration_id="migration",
        reason="shadow post-commit health signal failed",
    )
    assert rolled_back["migration"]["state"] == "ROLLED_BACK"
    assert rolled_back["runtime"]["active_candidate_id"] == "candidate-a"
    assert rolled_back["runtime"]["rollback_available"] is False


def test_orchestrator_abort_clears_pending_runtime_candidate() -> None:
    runtime, _migrations, orchestrator = _recommended_stack()
    orchestrator.plan_pending("session", migration_id="migration")
    aborted = orchestrator.abort("session", migration_id="migration", reason="verification worker rejected artifact")
    assert aborted["migration"]["state"] == "ABORTED"
    assert aborted["runtime"]["pending_candidate_id"] is None
