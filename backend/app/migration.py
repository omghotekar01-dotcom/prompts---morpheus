from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from typing import Any


class MigrationState(str, Enum):
    PLANNED = "PLANNED"
    SHADOW_BUILT = "SHADOW_BUILT"
    VERIFIED = "VERIFIED"
    COMMITTED = "COMMITTED"
    ROLLED_BACK = "ROLLED_BACK"
    ABORTED = "ABORTED"


@dataclass
class _MigrationRecord:
    migration_id: str
    session_id: str
    from_candidate_id: str
    to_candidate_id: str
    state: MigrationState = MigrationState.PLANNED
    artifact_sha256: str | None = None
    verification_manifest_sha256: str | None = None
    compile_verified: bool = False
    correctness_verified: bool = False
    rollback_candidate_id: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)


class MigrationController:
    """Safety-first migration lifecycle for a future runtime hot-swap worker.

    This controller deliberately does not move live process pointers or mutate a
    deployed data plane. It provides the state machine and invariants required
    before a worker is allowed to do so: plan -> shadow build -> verify ->
    commit, with abort and rollback paths. A real worker can later execute the
    physical operations behind these transitions without weakening the gates.
    """

    def __init__(self) -> None:
        self._records: dict[str, _MigrationRecord] = {}
        self._lock = RLock()

    def plan(
        self,
        migration_id: str,
        *,
        session_id: str,
        from_candidate_id: str,
        to_candidate_id: str,
    ) -> dict[str, Any]:
        if not migration_id or len(migration_id) > 128:
            raise ValueError("migration_id must contain 1-128 characters")
        if not session_id:
            raise ValueError("session_id is required")
        if not from_candidate_id or not to_candidate_id:
            raise ValueError("from_candidate_id and to_candidate_id are required")
        if from_candidate_id == to_candidate_id:
            raise ValueError("migration target must differ from active candidate")

        with self._lock:
            if migration_id in self._records:
                raise ValueError(f"migration already exists: {migration_id}")
            record = _MigrationRecord(
                migration_id=migration_id,
                session_id=session_id,
                from_candidate_id=from_candidate_id,
                to_candidate_id=to_candidate_id,
                rollback_candidate_id=from_candidate_id,
            )
            record.history.append(
                {
                    "kind": "migration_planned",
                    "from_candidate_id": from_candidate_id,
                    "to_candidate_id": to_candidate_id,
                }
            )
            self._records[migration_id] = record
            return self._view(record)

    def shadow_built(self, migration_id: str, *, artifact_sha256: str) -> dict[str, Any]:
        with self._lock:
            record = self._require(migration_id)
            self._require_state(record, MigrationState.PLANNED)
            if len(artifact_sha256) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in artifact_sha256):
                raise ValueError("artifact_sha256 must be a 64-character hexadecimal digest")
            record.artifact_sha256 = artifact_sha256.lower()
            record.state = MigrationState.SHADOW_BUILT
            record.history.append(
                {
                    "kind": "shadow_build_recorded",
                    "artifact_sha256": record.artifact_sha256,
                    "evidence_state": "SHADOW_ARTIFACT_RECORDED_NOT_YET_VERIFIED",
                }
            )
            return self._view(record)

    def verify(
        self,
        migration_id: str,
        *,
        compile_verified: bool,
        correctness_verified: bool,
        verification_manifest_sha256: str,
    ) -> dict[str, Any]:
        with self._lock:
            record = self._require(migration_id)
            self._require_state(record, MigrationState.SHADOW_BUILT)
            if len(verification_manifest_sha256) != 64 or any(
                ch not in "0123456789abcdefABCDEF" for ch in verification_manifest_sha256
            ):
                raise ValueError("verification_manifest_sha256 must be a 64-character hexadecimal digest")

            record.compile_verified = compile_verified
            record.correctness_verified = correctness_verified
            record.verification_manifest_sha256 = verification_manifest_sha256.lower()
            record.history.append(
                {
                    "kind": "verification_recorded",
                    "compile_verified": compile_verified,
                    "correctness_verified": correctness_verified,
                    "verification_manifest_sha256": record.verification_manifest_sha256,
                }
            )
            if compile_verified and correctness_verified:
                record.state = MigrationState.VERIFIED
            return self._view(record)

    def commit(self, migration_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._require(migration_id)
            self._require_state(record, MigrationState.VERIFIED)
            if not record.compile_verified or not record.correctness_verified:
                raise ValueError("migration cannot commit without compile and correctness verification")
            record.state = MigrationState.COMMITTED
            record.history.append(
                {
                    "kind": "commit_authorized",
                    "active_candidate_id": record.to_candidate_id,
                    "evidence_state": "CONTROL_PLANE_COMMIT_AUTHORIZED_NO_PROCESS_SWAP",
                }
            )
            return self._view(record)

    def rollback(self, migration_id: str, *, reason: str) -> dict[str, Any]:
        with self._lock:
            record = self._require(migration_id)
            self._require_state(record, MigrationState.COMMITTED)
            if not reason:
                raise ValueError("rollback reason is required")
            record.state = MigrationState.ROLLED_BACK
            record.history.append(
                {
                    "kind": "rollback_authorized",
                    "reason": reason,
                    "restore_candidate_id": record.rollback_candidate_id,
                    "evidence_state": "CONTROL_PLANE_ROLLBACK_AUTHORIZED_NO_PROCESS_SWAP",
                }
            )
            return self._view(record)

    def abort(self, migration_id: str, *, reason: str) -> dict[str, Any]:
        with self._lock:
            record = self._require(migration_id)
            if record.state in {MigrationState.COMMITTED, MigrationState.ROLLED_BACK, MigrationState.ABORTED}:
                raise ValueError(f"cannot abort migration in state {record.state.value}")
            if not reason:
                raise ValueError("abort reason is required")
            record.state = MigrationState.ABORTED
            record.history.append({"kind": "migration_aborted", "reason": reason})
            return self._view(record)

    def get(self, migration_id: str) -> dict[str, Any]:
        with self._lock:
            return self._view(self._require(migration_id))

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._view(self._records[key]) for key in sorted(self._records)]

    def _require(self, migration_id: str) -> _MigrationRecord:
        try:
            return self._records[migration_id]
        except KeyError as exc:
            raise KeyError(f"unknown migration: {migration_id}") from exc

    @staticmethod
    def _require_state(record: _MigrationRecord, expected: MigrationState) -> None:
        if record.state != expected:
            raise ValueError(
                f"migration {record.migration_id} must be in state {expected.value}; current={record.state.value}"
            )

    @staticmethod
    def _view(record: _MigrationRecord) -> dict[str, Any]:
        return {
            "migration_id": record.migration_id,
            "session_id": record.session_id,
            "from_candidate_id": record.from_candidate_id,
            "to_candidate_id": record.to_candidate_id,
            "state": record.state.value,
            "artifact_sha256": record.artifact_sha256,
            "verification_manifest_sha256": record.verification_manifest_sha256,
            "compile_verified": record.compile_verified,
            "correctness_verified": record.correctness_verified,
            "rollback_candidate_id": record.rollback_candidate_id,
            "history": list(record.history),
            "evidence_state": "MIGRATION_CONTROL_PLANE_ONLY_NO_LIVE_PROCESS_SWAP",
        }


MIGRATIONS = MigrationController()
