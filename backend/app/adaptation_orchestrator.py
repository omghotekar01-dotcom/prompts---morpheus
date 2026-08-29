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

    Multi-controller transitions use fail-closed preconditions plus best-effort
    compensation. The controllers are in-process objects rather than one shared
    transactional database, so MORPHEUS must never describe this as a distributed
    atomic transaction.
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

    def _compensate_failed_commit(
        self,
        *,
        session_id: str,
        migration_id: str,
        deployment_id: str | None,
        from_candidate_id: str,
        to_candidate_id: str,
        cause: Exception,
    ) -> None:
        """Try every safe compensation leg before propagating a commit failure.

        A failure can happen after one controller has already changed state. We
        inspect actual state rather than relying only on local boolean flags so a
        fault injected immediately after a state mutation is still recoverable.
        """

        compensation_errors: list[str] = []
        reason = f"commit compensation after {type(cause).__name__}"

        if deployment_id is not None and self.dataplane is not None:
            try:
                deployment = self.dataplane.get(deployment_id)
                if (
                    deployment["active"]["candidate_id"] == to_candidate_id
                    and int(deployment.get("rollback_depth", 0)) > 0
                ):
                    self.dataplane.rollback(deployment_id, reason=reason)
            except Exception as exc:  # compensation must continue through every leg
                compensation_errors.append(f"data_plane:{type(exc).__name__}:{exc}")

        try:
            runtime_state = self.runtime.get(session_id)
            if (
                runtime_state.get("active_candidate_id") == to_candidate_id
                and runtime_state.get("rollback_available") is True
            ):
                self.runtime.rollback_last_switch(session_id, reason=reason)
        except Exception as exc:
            compensation_errors.append(f"runtime:{type(exc).__name__}:{exc}")

        try:
            migration_state = self.migrations.get(migration_id)
            if migration_state.get("state") == MigrationState.COMMITTED.value:
                self.migrations.rollback(migration_id, reason=reason)
        except Exception as exc:
            compensation_errors.append(f"migration:{type(exc).__name__}:{exc}")

        # Verify the safety-critical identities after compensation. A VERIFIED
        # migration is allowed because it has not been committed; COMMITTED is not.
        try:
            runtime_state = self.runtime.get(session_id)
            if runtime_state.get("active_candidate_id") != from_candidate_id:
                compensation_errors.append(
                    f"runtime:active_candidate={runtime_state.get('active_candidate_id')} expected={from_candidate_id}"
                )
        except Exception as exc:
            compensation_errors.append(f"runtime_verify:{type(exc).__name__}:{exc}")

        if deployment_id is not None and self.dataplane is not None:
            try:
                deployment = self.dataplane.get(deployment_id)
                if deployment["active"]["candidate_id"] != from_candidate_id:
                    compensation_errors.append(
                        f"data_plane:active_candidate={deployment['active']['candidate_id']} expected={from_candidate_id}"
                    )
            except Exception as exc:
                compensation_errors.append(f"data_plane_verify:{type(exc).__name__}:{exc}")

        if compensation_errors:
            raise RuntimeError(
                "adaptation commit failed and compensation did not restore a consistent source candidate: "
                + " | ".join(compensation_errors)
            ) from cause

    def authorize_commit(self, session_id: str, *, migration_id: str) -> dict[str, Any]:
        """Commit a verified adaptation with compensating failure recovery.

        Order matters: local routing is activated, runtime state is confirmed,
        and the migration ledger is marked COMMITTED last. If either later leg
        fails, MORPHEUS restores any already-mutated runtime/data-plane state.
        This avoids leaving a migration recorded as COMMITTED while the runtime
        has actually returned to the old candidate.
        """

        with self._lock:
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
            if deployment_id is not None:
                if self.dataplane is None:
                    raise ValueError("bound deployment exists but no data-plane router is configured")
                data_plane_state = self.dataplane.activate(
                    deployment_id,
                    expected_from_candidate_id=str(migration["from_candidate_id"]),
                    expected_to_candidate_id=str(migration["to_candidate_id"]),
                )

            try:
                # Confirm runtime before marking the migration COMMITTED. Runtime
                # confirm is reversible; an already-COMMITTED migration would
                # otherwise misrepresent a later runtime-confirm failure.
                confirmed = self.runtime.confirm(session_id, candidate_id=str(migration["to_candidate_id"]))
                committed = self.migrations.commit(migration_id)
            except Exception as exc:
                self._compensate_failed_commit(
                    session_id=session_id,
                    migration_id=migration_id,
                    deployment_id=deployment_id,
                    from_candidate_id=str(migration["from_candidate_id"]),
                    to_candidate_id=str(migration["to_candidate_id"]),
                    cause=exc,
                )
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
                    "When data_plane is present, the active local artifact route changed atomically and the in-process controllers completed their guarded commit sequence. "
                    "This is compensating in-process coordination, not a distributed transaction or native cross-process hot swap."
                ),
            }

    def abort(self, session_id: str, *, migration_id: str, reason: str) -> dict[str, Any]:
        migration_before = self.migrations.get(migration_id)
        if migration_before["session_id"] != session_id:
            raise ValueError("migration does not belong to runtime session")
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
        if not reason:
            raise ValueError("rollback reason is required")
        with self._lock:
            migration_before = self.migrations.get(migration_id)
            if migration_before["session_id"] != session_id:
                raise ValueError("migration does not belong to runtime session")
            if migration_before["state"] != MigrationState.COMMITTED.value:
                raise ValueError("migration must be COMMITTED before rollback")

            runtime_before = self.runtime.get(session_id)
            if runtime_before.get("active_candidate_id") != migration_before["to_candidate_id"]:
                raise ValueError("runtime active candidate does not match committed migration target")
            if not runtime_before.get("rollback_available"):
                raise ValueError("runtime session has no matching rollback checkpoint")

            deployment_id = self.deployment_for_session(session_id)
            if deployment_id is not None:
                if self.dataplane is None:
                    raise ValueError("bound deployment exists but no data-plane router is configured")
                deployment_before = self.dataplane.get(deployment_id)
                if deployment_before["active"]["candidate_id"] != migration_before["to_candidate_id"]:
                    raise ValueError("data-plane active candidate does not match committed migration target")
                if int(deployment_before.get("rollback_depth", 0)) < 1:
                    raise ValueError("data-plane deployment has no matching rollback checkpoint")

            # All local preconditions are checked before the first mutation.
            data_plane: dict[str, Any] | None = None
            if deployment_id is not None and self.dataplane is not None:
                data_plane = self.dataplane.rollback(deployment_id, reason=reason)
            runtime = self.runtime.rollback_last_switch(session_id, reason=reason)
            migration = self.migrations.rollback(migration_id, reason=reason)
            return {
                "migration": migration,
                "runtime": runtime,
                "data_plane": data_plane,
                "evidence_state": (
                    "LOCAL_IN_PROCESS_DATA_PLANE_AND_CONTROL_PLANE_ROLLED_BACK"
                    if data_plane is not None
                    else "CONTROL_PLANE_ADAPTATION_ROLLED_BACK_NO_LIVE_SWAP"
                ),
                "truth_boundary": (
                    "Rollback preconditions are checked across the local controllers before mutation. "
                    "The operation remains in-process coordination, not a distributed ACID transaction."
                ),
            }
