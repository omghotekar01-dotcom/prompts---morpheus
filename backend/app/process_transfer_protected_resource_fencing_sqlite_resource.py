from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from app.process_transfer_protected_resource_fencing_sqlite import SQLiteAtomicConditionalFencingBackend


EVIDENCE_STATE = "SQLITE_TRANSACTIONALLY_FENCED_LOCAL_PROTECTED_RESOURCE_REFERENCE_EVIDENCE"
TRUTH_BOUNDARY = (
    "This module is a local SQLite reference adapter that binds fencing-state validation/advance and one minimal protected-resource "
    "mutation inside the same SQLite transaction. Its evidence is limited to the exercised local SQLite database paths. It does not "
    "establish atomicity or fencing enforcement for arbitrary external resources, distributed linearizability, cross-host consensus, "
    "leases, network-partition behavior, storage-device durability, power-loss survival, safe cutover, live replacement, activation, "
    "production traffic switching, HA/SLA behavior or production readiness, and makes no benchmark, performance, novelty, patentability "
    "or scientific-effect claim."
)

_RESOURCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS morpheus_protected_resource_state (
    resource_id TEXT NOT NULL,
    fencing_authority_id TEXT NOT NULL,
    resource_version INTEGER NOT NULL CHECK (resource_version >= 1),
    value TEXT NOT NULL,
    last_mutation_id TEXT NOT NULL,
    last_fencing_counter INTEGER NOT NULL CHECK (last_fencing_counter >= 0),
    PRIMARY KEY (resource_id, fencing_authority_id)
)
"""


def _identity(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _counter(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("fencing_counter must be a non-negative integer")
    return value


@dataclass(frozen=True)
class SQLiteProtectedResourceSnapshot:
    resource_id: str
    fencing_authority_id: str
    resource_version: int
    value: str
    last_mutation_id: str
    last_fencing_counter: int


@dataclass(frozen=True)
class SQLiteProtectedResourceMutationResult:
    resource_id: str
    fencing_authority_id: str
    requested_fencing_counter: int
    mutation_id: str
    outcome: str
    accepted: bool
    state_changed: bool
    fencing_version: int | None
    resource_version: int | None
    value: str | None
    automatic_control_allowed: bool
    activation_allowed: bool
    traffic_switching_allowed: bool
    evidence_state: str
    truth_boundary: str


class SQLiteTransactionallyFencedProtectedResource:
    """Minimal SQLite protected-resource reference path bound atomically to fencing state.

    The fencing row and resource row are read and, when accepted, changed under one ``BEGIN IMMEDIATE`` transaction. Equal-generation
    retries are accepted only when the mutation id and value exactly replay the last committed mutation; reuse of the same fencing
    generation for a different mutation fails closed.
    """

    def __init__(self, database_path: str | Path, *, timeout_seconds: float = 5.0) -> None:
        self._fencing = SQLiteAtomicConditionalFencingBackend(database_path, timeout_seconds=timeout_seconds)
        self.database_path = self._fencing.database_path
        self.timeout_seconds = self._fencing.timeout_seconds
        try:
            with self._connect() as connection:
                connection.execute(_RESOURCE_SCHEMA)
        except sqlite3.Error as exc:
            raise ValueError("failed to initialize SQLite protected resource") from exc

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database_path), timeout=self.timeout_seconds, isolation_level=None)
        connection.execute(f"PRAGMA busy_timeout = {max(1, int(self.timeout_seconds * 1000))}")
        return connection

    @staticmethod
    def _resource_snapshot(resource_id: str, fencing_authority_id: str, row: tuple[object, ...] | None) -> SQLiteProtectedResourceSnapshot | None:
        if row is None:
            return None
        resource_version, value, mutation_id, fencing_counter = row
        if not isinstance(resource_version, int) or isinstance(resource_version, bool) or resource_version < 1:
            raise ValueError("persisted resource_version must be a positive integer")
        if not isinstance(value, str):
            raise ValueError("persisted protected-resource value must be text")
        mutation_id = _identity(mutation_id, "persisted last_mutation_id")  # type: ignore[arg-type]
        fencing_counter = _counter(fencing_counter)  # type: ignore[arg-type]
        return SQLiteProtectedResourceSnapshot(
            resource_id, fencing_authority_id, resource_version, value, mutation_id, fencing_counter
        )

    def snapshot(self, resource_id: str, fencing_authority_id: str) -> SQLiteProtectedResourceSnapshot | None:
        resource_id = _identity(resource_id, "resource_id")
        fencing_authority_id = _identity(fencing_authority_id, "fencing_authority_id")
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT resource_version, value, last_mutation_id, last_fencing_counter "
                    "FROM morpheus_protected_resource_state WHERE resource_id = ? AND fencing_authority_id = ?",
                    (resource_id, fencing_authority_id),
                ).fetchone()
        except sqlite3.Error as exc:
            raise ValueError("SQLite protected-resource snapshot failed") from exc
        return self._resource_snapshot(resource_id, fencing_authority_id, row)

    def mutate(
        self,
        resource_id: str,
        fencing_authority_id: str,
        fencing_counter: int,
        *,
        mutation_id: str,
        value: str,
    ) -> SQLiteProtectedResourceMutationResult:
        resource_id = _identity(resource_id, "resource_id")
        fencing_authority_id = _identity(fencing_authority_id, "fencing_authority_id")
        fencing_counter = _counter(fencing_counter)
        mutation_id = _identity(mutation_id, "mutation_id")
        if not isinstance(value, str):
            raise ValueError("value must be text")

        try:
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                fencing_row = connection.execute(
                    "SELECT fencing_counter, version FROM morpheus_fencing_state WHERE resource_id = ? AND fencing_authority_id = ?",
                    (resource_id, fencing_authority_id),
                ).fetchone()
                resource_row = connection.execute(
                    "SELECT resource_version, value, last_mutation_id, last_fencing_counter "
                    "FROM morpheus_protected_resource_state WHERE resource_id = ? AND fencing_authority_id = ?",
                    (resource_id, fencing_authority_id),
                ).fetchone()
                resource = self._resource_snapshot(resource_id, fencing_authority_id, resource_row)

                current_counter = None if fencing_row is None else fencing_row[0]
                current_fencing_version = None if fencing_row is None else fencing_row[1]
                if current_counter is not None:
                    current_counter = _counter(current_counter)
                if current_fencing_version is not None and (
                    not isinstance(current_fencing_version, int)
                    or isinstance(current_fencing_version, bool)
                    or current_fencing_version < 1
                ):
                    raise ValueError("persisted fencing version must be a positive integer")

                if current_counter is not None and fencing_counter < current_counter:
                    outcome = "stale"
                    accepted = False
                    state_changed = False
                elif current_counter is not None and fencing_counter == current_counter:
                    if (
                        resource is not None
                        and resource.last_fencing_counter == fencing_counter
                        and resource.last_mutation_id == mutation_id
                        and resource.value == value
                    ):
                        outcome = "idempotent"
                        accepted = True
                    else:
                        outcome = "generation_reuse_rejected"
                        accepted = False
                    state_changed = False
                else:
                    next_fencing_version = 1 if current_fencing_version is None else current_fencing_version + 1
                    if fencing_row is None:
                        connection.execute(
                            "INSERT INTO morpheus_fencing_state(resource_id, fencing_authority_id, fencing_counter, version) VALUES (?, ?, ?, ?)",
                            (resource_id, fencing_authority_id, fencing_counter, next_fencing_version),
                        )
                    else:
                        cursor = connection.execute(
                            "UPDATE morpheus_fencing_state SET fencing_counter = ?, version = ? "
                            "WHERE resource_id = ? AND fencing_authority_id = ? AND version = ?",
                            (fencing_counter, next_fencing_version, resource_id, fencing_authority_id, current_fencing_version),
                        )
                        if cursor.rowcount != 1:
                            raise ValueError("SQLite protected-resource fencing predecessor changed")

                    next_resource_version = 1 if resource is None else resource.resource_version + 1
                    if resource is None:
                        connection.execute(
                            "INSERT INTO morpheus_protected_resource_state(resource_id, fencing_authority_id, resource_version, value, "
                            "last_mutation_id, last_fencing_counter) VALUES (?, ?, ?, ?, ?, ?)",
                            (resource_id, fencing_authority_id, next_resource_version, value, mutation_id, fencing_counter),
                        )
                    else:
                        cursor = connection.execute(
                            "UPDATE morpheus_protected_resource_state SET resource_version = ?, value = ?, last_mutation_id = ?, "
                            "last_fencing_counter = ? WHERE resource_id = ? AND fencing_authority_id = ? AND resource_version = ?",
                            (
                                next_resource_version,
                                value,
                                mutation_id,
                                fencing_counter,
                                resource_id,
                                fencing_authority_id,
                                resource.resource_version,
                            ),
                        )
                        if cursor.rowcount != 1:
                            raise ValueError("SQLite protected-resource predecessor changed")
                    current_fencing_version = next_fencing_version
                    resource = SQLiteProtectedResourceSnapshot(
                        resource_id,
                        fencing_authority_id,
                        next_resource_version,
                        value,
                        mutation_id,
                        fencing_counter,
                    )
                    outcome = "applied"
                    accepted = True
                    state_changed = True

                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()
        except ValueError:
            raise
        except sqlite3.Error as exc:
            raise ValueError("SQLite transactionally fenced protected-resource mutation failed") from exc

        return SQLiteProtectedResourceMutationResult(
            resource_id=resource_id,
            fencing_authority_id=fencing_authority_id,
            requested_fencing_counter=fencing_counter,
            mutation_id=mutation_id,
            outcome=outcome,
            accepted=accepted,
            state_changed=state_changed,
            fencing_version=current_fencing_version,
            resource_version=None if resource is None else resource.resource_version,
            value=None if resource is None else resource.value,
            automatic_control_allowed=False,
            activation_allowed=False,
            traffic_switching_allowed=False,
            evidence_state=EVIDENCE_STATE,
            truth_boundary=TRUTH_BOUNDARY,
        )
