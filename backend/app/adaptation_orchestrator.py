from __future__ import annotations

from typing import Any

from .migration import MigrationController
from .runtime import RuntimeController


class SafeAdaptationOrchestrator:
    """Bind runtime recommendations to the gated migration state machine.

    The orchestrator prevents a runtime recommendation from being confirmed in
    control-plane state until a matching migration has reached VERIFIED and its
    commit has been authorized. This is still not a live process/data-plane
    swap; it is the deterministic safety protocol that a deployment worker must
    satisfy before performing one.
    """

    def __init__(self, runtime: RuntimeController, migrations: MigrationController) -> None:
        self.runtime = runtime
        self.migrations = migrations

    def plan_pending(self, session_id: str, *, migration_id: str) -> dict[str, Any]:
        session = self.runtime.get(session_id)
        pending = session.get("pending_candidate_id")
        if not pending:
            raise ValueError("runtime session has no pending switch recommendation")
        return self.migrations.plan(
            migration_id,
            session_id=session_id,
            from_candidate_id=str(session["active_candidate_id"]),
            to_candidate_id=str(pending),
        )

    def authorize_commit(self, session_id: str, *, migration_id: str) -> dict[str, Any]:
        migration = self.migrations.get(migration_id)
        if migration["session_id"] != session_id:
            raise ValueError("migration does not belong to runtime session")
        session = self.runtime.get(session_id)
        if session.get("pending_candidate_id") != migration["to_candidate_id"]:
            raise ValueError("runtime pending candidate no longer matches migration target")
        if session.get("active_candidate_id") != migration["from_candidate_id"]:
            raise ValueError("runtime active candidate no longer matches migration source")

        committed = self.migrations.commit(migration_id)
        confirmed = self.runtime.confirm(session_id, candidate_id=str(migration["to_candidate_id"]))
        return {
            "migration": committed,
            "runtime": confirmed,
            "evidence_state": "CONTROL_PLANE_MIGRATION_AND_RUNTIME_COMMIT_NO_LIVE_SWAP",
        }

    def abort(self, session_id: str, *, migration_id: str, reason: str) -> dict[str, Any]:
        migration = self.migrations.abort(migration_id, reason=reason)
        runtime = self.runtime.abort_pending(session_id, reason=reason)
        return {
            "migration": migration,
            "runtime": runtime,
            "evidence_state": "CONTROL_PLANE_ADAPTATION_ABORTED",
        }

    def rollback(self, session_id: str, *, migration_id: str, reason: str) -> dict[str, Any]:
        migration = self.migrations.rollback(migration_id, reason=reason)
        runtime = self.runtime.rollback_last_switch(session_id, reason=reason)
        return {
            "migration": migration,
            "runtime": runtime,
            "evidence_state": "CONTROL_PLANE_ADAPTATION_ROLLED_BACK_NO_LIVE_SWAP",
        }
