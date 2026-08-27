from __future__ import annotations

from threading import RLock
from typing import Any

from .dataplane import VersionedArtifactRouter
from .migration import MigrationController, MigrationState
from .runtime import RuntimeController


class SafeAdaptationOrchestrator:
    """Bind runtime recommendations, verification gates and optional local data-plane routing.

    Without a `VersionedArtifactRouter` this behaves as the original control-plane
    protocol. When a router is supplied and a runtime session is explicitly bound
    to a deployment, VERIFIED migrations can stage and atomically activate a local
    artifact version before the runtime candidate is confirmed. That proves an
    in-process versioned routing mechanism, not native-object/cross-process migration.
    """

    def __init__(
        self,
        runtime: RuntimeController,
        migrations: MigrationController,
        dataplane: VersionedArtifactRouter | None = None,
    ) -> None:
        self.runtime = runtime
        self.migrations = migrations
        self.dataplane = dataplane
        self._session_deployments: dict[str, str] = {}
        self._lock = RLock()

    def bind_deployment(self, session_id: str, *, deployment_id: str) -> dict[str, Any]:
        if self.dataplane is None:
            raise ValueError("no data-plane router is configured")
        session = self.runtime.get(session_id)
        deployment = self.dataplane.get(deployment_id)
        if deployment["active"]["candidate_id"] != session["active_candidate_id"]:
            raise ValueError("deployment active candidate does not match runtime session")
        with self._lock:
            self._session_deployments[session_id] = deployment_id
        return {
            "session_id": session_id,
            "deployment_id": deployment_id,
            "active_candidate_id": session["active_candidate_id"],
            "evidence_state": "LOCAL_RUNTIME_SESSION_BOUND_TO_VERSIONED_ARTIFACT_ROUTER",
        }

    def deployment_for_session(self, session_id: str) -> str | None:
        with self._lock:
            return self._session_deployments.get(session_id)

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

    def stage_verified_migration(self, migration_id: str) -> dict[str, Any]:
        """Stage a VERIFIED migration in the bound local data-plane router."""

        if self.dataplane is None:
            raise ValueError("no data-plane router is configured")
        migration = self.migrations.get(migration_id)
        if migration["state"] != MigrationState.VERIFIED.value:
            raise ValueError("migration must be VERIFIED before data-plane staging")
        if not migration.get("artifact_sha256") or not migration.get("verification_manifest_sha256"):
            raise ValueError("verified migration is missing artifact or verification identity")
        deployment_id = self.deployment_for_session(str(migration["session_id"]))
        if deployment_id is None:
            raise ValueError("runtime session is not bound to a data-plane deployment")
        deployment = self.dataplane.stage(
            deployment_id,
            candidate_id=str(migration["to_candidate_id"]),
            artifact_sha256=str(migration["artifact_sha256"]),
            verification_manifest_sha256=str(migration["verification_manifest_sha256"]),
            metadata={"migration_id": migration_id, "session_id": migration["session_id"]},
        )
        return {
            "migration": migration,
            "deployment": deployment,
            "evidence_state": "VERIFIED_MIGRATION_STAGED_IN_LOCAL_DATA_PLANE",
        }

    def authorize_commit(self, session_id: str, *, migration_id: str) -> dict[str, Any]:
        migration = self.migrations.get(migration_id)
        if migration["session_id"] != session_id:
            raise ValueError("migration does not belong to runtime session")
        session = self.runtime.get(session_id)
        if session.get("pending_candidate_id") != migration["to_candidate_id"]:
            raise ValueError("runtime pending candidate no longer matches migration target")
        if session.get("active_candidate_id") != migration["from_candidate_id"]:
            raise ValueError("runtime active candidate no longer matches migration source")
        if migration["state"] != MigrationState.VERIFIED.value:
            raise ValueError("migration must be VERIFIED before commit")

        deployment_id = self.deployment_for_session(session_id)
        data_plane_state: dict[str, Any] | None = None
        data_plane_activated = False
        if deployment_id is not None:
            if self.dataplane is None:
                raise ValueError("bound deployment exists but no data-plane router is configured")
            data_plane_state = self.dataplane.activate(
                deployment_id,
                expected_from_candidate_id=str(migration["from_candidate_id"]),
                expected_to_candidate_id=str(migration["to_candidate_id"]),
            )
            data_plane_activated = True

        try:
            committed = self.migrations.commit(migration_id)
            confirmed = self.runtime.confirm(session_id, candidate_id=str(migration["to_candidate_id"]))
        except Exception:
            if data_plane_activated and deployment_id is not None and self.dataplane is not None:
                self.dataplane.rollback(deployment_id, reason="control-plane commit failed after local activation")
            raise

        return {
            "migration": committed,
            "runtime": confirmed,
            "data_plane": data_plane_state,
            "evidence_state": (
                "LOCAL_IN_PROCESS_DATA_PLANE_AND_CONTROL_PLANE_COMMITTED"
                if data_plane_state is not None
                else "CONTROL_PLANE_MIGRATION_AND_RUNTIME_COMMIT_NO_LIVE_SWAP"
            ),
            "truth_boundary": (
                "When data_plane is present, the active local artifact route changed atomically; native generated-object migration and cross-process hot swap are still not established."
            ),
        }

    def abort(self, session_id: str, *, migration_id: str, reason: str) -> dict[str, Any]:
        migration_before = self.migrations.get(migration_id)
        deployment_id = self.deployment_for_session(session_id)
        data_plane: dict[str, Any] | None = None
        if deployment_id is not None and self.dataplane is not None:
            current = self.dataplane.get(deployment_id)
            staged = current.get("staged")
            if staged and staged.get("candidate_id") == migration_before.get("to_candidate_id"):
                data_plane = self.dataplane.abort_staged(deployment_id, reason=reason)
        migration = self.migrations.abort(migration_id, reason=reason)
        runtime = self.runtime.abort_pending(session_id, reason=reason)
        return {
            "migration": migration,
            "runtime": runtime,
            "data_plane": data_plane,
            "evidence_state": "ADAPTATION_ABORTED_WITH_LOCAL_STAGE_CLEANUP" if data_plane else "CONTROL_PLANE_ADAPTATION_ABORTED",
        }

    def rollback(self, session_id: str, *, migration_id: str, reason: str) -> dict[str, Any]:
        migration_before = self.migrations.get(migration_id)
        if migration_before["session_id"] != session_id:
            raise ValueError("migration does not belong to runtime session")
        deployment_id = self.deployment_for_session(session_id)
        data_plane: dict[str, Any] | None = None
        if deployment_id is not None:
            if self.dataplane is None:
                raise ValueError("bound deployment exists but no data-plane router is configured")
            data_plane = self.dataplane.rollback(deployment_id, reason=reason)
        migration = self.migrations.rollback(migration_id, reason=reason)
        runtime = self.runtime.rollback_last_switch(session_id, reason=reason)
        return {
            "migration": migration,
            "runtime": runtime,
            "data_plane": data_plane,
            "evidence_state": (
                "LOCAL_IN_PROCESS_DATA_PLANE_AND_CONTROL_PLANE_ROLLED_BACK"
                if data_plane is not None
                else "CONTROL_PLANE_ADAPTATION_ROLLED_BACK_NO_LIVE_SWAP"
            ),
        }
