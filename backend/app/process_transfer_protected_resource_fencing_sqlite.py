from __future__ import annotations

import sqlite3
from pathlib import Path

from app.process_transfer_protected_resource_fencing_atomic import (
    AtomicFencingSnapshot,
    AtomicFencingTransitionResult,
)


EVIDENCE_STATE = "SQLITE_TRANSACTIONAL_CONDITIONAL_FENCING_BACKEND_LOCAL_DATABASE_EVIDENCE"
TRUTH_BOUNDARY = (
    "This module is a concrete SQLite adapter for the MORPHEUS atomic conditional fencing contract. Its evidence is limited to SQLite "
    "transactions against one local database file as exercised by MORPHEUS tests. It does not establish distributed linearizability, "
    "cross-host consensus, leases, network-store correctness, cloud-database semantics, storage-device durability, power-loss survival, "
    "protected-resource enforcement, safe cutover, activation, production traffic switching, HA/SLA behavior or production readiness, "
    "and makes no benchmark, performance, novelty, patentability or scientific-effect claim."
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS morpheus_fencing_state (
    resource_id TEXT NOT NULL,
    fencing_authority_id TEXT NOT NULL,
    fencing_counter INTEGER NOT NULL CHECK (fencing_counter >= 0),
    version INTEGER NOT NULL CHECK (version >= 1),
    PRIMARY KEY (resource_id, fencing_authority_id)
)
"""


def _identity(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _counter(value: int, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _version(value: int | None, field: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{field} must be None or a positive integer")
    return value


class SQLiteAtomicConditionalFencingBackend:
    """SQLite-backed implementation of the E16 conditional fencing contract.

    Each operation opens its own connection. ``conditional_write`` uses ``BEGIN IMMEDIATE`` so the read/decision/write sequence is one
    SQLite transaction. The scope of that statement is SQLite's transaction behavior for the configured local database, not a claim
    about distributed stores or the protected resource itself.
    """

    def __init__(self, database_path: str | Path, *, timeout_seconds: float = 5.0) -> None:
        if isinstance(database_path, bool) or not isinstance(database_path, (str, Path)):
            raise ValueError("database_path must be a filesystem path")
        candidate_path = Path(database_path)
        if not candidate_path.name:
            raise ValueError("database_path must name a database file")
        self.database_path = candidate_path.resolve()
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.timeout_seconds = float(timeout_seconds)
        parent = self.database_path.parent
        if not parent.exists() or not parent.is_dir():
            raise ValueError("database parent directory must already exist")
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database_path), timeout=self.timeout_seconds, isolation_level=None)
        connection.execute(f"PRAGMA busy_timeout = {max(1, int(self.timeout_seconds * 1000))}")
        return connection

    def _initialize_schema(self) -> None:
        try:
            with self._connect() as connection:
                connection.execute(_SCHEMA)
        except sqlite3.Error as exc:
            raise ValueError("failed to initialize SQLite fencing backend") from exc

    @staticmethod
    def _snapshot_from_row(resource_id: str, fencing_authority_id: str, row: tuple[object, object] | None) -> AtomicFencingSnapshot | None:
        if row is None:
            return None
        fencing_counter = _counter(row[0], "persisted fencing_counter")  # type: ignore[arg-type]
        version = _version(row[1], "persisted version")
        if version is None:  # pragma: no cover - _version rejects persisted None via the check below
            raise ValueError("persisted version must be a positive integer")
        return AtomicFencingSnapshot(resource_id, fencing_authority_id, fencing_counter, version)

    def snapshot(self, resource_id: str, fencing_authority_id: str) -> AtomicFencingSnapshot | None:
        resource_id = _identity(resource_id, "resource_id")
        fencing_authority_id = _identity(fencing_authority_id, "fencing_authority_id")
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT fencing_counter, version FROM morpheus_fencing_state WHERE resource_id = ? AND fencing_authority_id = ?",
                    (resource_id, fencing_authority_id),
                ).fetchone()
        except sqlite3.Error as exc:
            raise ValueError("SQLite fencing snapshot failed") from exc
        return self._snapshot_from_row(resource_id, fencing_authority_id, row)

    def conditional_write(
        self,
        resource_id: str,
        fencing_authority_id: str,
        fencing_counter: int,
        *,
        expected_version: int | None,
    ) -> AtomicFencingTransitionResult:
        resource_id = _identity(resource_id, "resource_id")
        fencing_authority_id = _identity(fencing_authority_id, "fencing_authority_id")
        fencing_counter = _counter(fencing_counter, "fencing_counter")
        expected_version = _version(expected_version, "expected_version")

        try:
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT fencing_counter, version FROM morpheus_fencing_state WHERE resource_id = ? AND fencing_authority_id = ?",
                    (resource_id, fencing_authority_id),
                ).fetchone()
                current = self._snapshot_from_row(resource_id, fencing_authority_id, row)
                observed_counter = None if current is None else current.fencing_counter
                observed_version = None if current is None else current.version

                if current is not None and fencing_counter < current.fencing_counter:
                    outcome = "stale"
                elif current is not None and fencing_counter == current.fencing_counter:
                    outcome = "idempotent"
                elif observed_version != expected_version:
                    outcome = "conflict"
                else:
                    next_version = 1 if current is None else current.version + 1
                    if current is None:
                        connection.execute(
                            "INSERT INTO morpheus_fencing_state(resource_id, fencing_authority_id, fencing_counter, version) VALUES (?, ?, ?, ?)",
                            (resource_id, fencing_authority_id, fencing_counter, next_version),
                        )
                    else:
                        cursor = connection.execute(
                            "UPDATE morpheus_fencing_state SET fencing_counter = ?, version = ? WHERE resource_id = ? AND fencing_authority_id = ? AND version = ?",
                            (fencing_counter, next_version, resource_id, fencing_authority_id, current.version),
                        )
                        if cursor.rowcount != 1:
                            raise ValueError("SQLite fencing conditional update lost predecessor identity")
                    observed_counter = fencing_counter
                    observed_version = next_version
                    outcome = "applied"

                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()
        except ValueError:
            raise
        except sqlite3.Error as exc:
            raise ValueError("SQLite fencing conditional write failed") from exc

        return AtomicFencingTransitionResult(
            resource_id=resource_id,
            fencing_authority_id=fencing_authority_id,
            requested_fencing_counter=fencing_counter,
            expected_version=expected_version,
            observed_fencing_counter=observed_counter,
            observed_version=observed_version,
            outcome=outcome,
            accepted=outcome in {"applied", "idempotent"},
            state_changed=outcome == "applied",
            automatic_control_allowed=False,
            activation_allowed=False,
            traffic_switching_allowed=False,
            evidence_state=EVIDENCE_STATE,
            truth_boundary=TRUTH_BOUNDARY,
        )
