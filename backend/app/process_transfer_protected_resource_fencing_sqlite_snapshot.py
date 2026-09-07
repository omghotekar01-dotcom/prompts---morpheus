from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from app.process_transfer_protected_resource_fencing_atomic import AtomicFencingSnapshot
from app.process_transfer_protected_resource_fencing_sqlite_resource import (
    SQLiteProtectedResourceSnapshot,
    SQLiteTransactionallyFencedProtectedResource,
)


EVIDENCE_STATE = "SQLITE_TRANSACTION_CONSISTENT_FENCING_RESOURCE_SNAPSHOT_REFERENCE"
TRUTH_BOUNDARY = (
    "This module provides a local SQLite read-transaction reference path for observing one fencing row and its protected-resource row "
    "from the same SQLite transaction snapshot. Its evidence is limited to exercised local SQLite database paths. It does not establish "
    "distributed snapshot isolation, serializability for unrelated databases, cross-host linearizability, external-resource consistency, "
    "network-partition safety, power-loss durability, production failover, activation authority, traffic-switching authority, HA/SLA "
    "behavior or production readiness, and makes no benchmark, performance, novelty, patentability or scientific-effect claim."
)


def _identity(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _positive_version(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _non_negative_counter(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


@dataclass(frozen=True)
class SQLiteFencingResourceSnapshotPair:
    resource_id: str
    fencing_authority_id: str
    fencing: AtomicFencingSnapshot
    resource: SQLiteProtectedResourceSnapshot
    automatic_control_allowed: bool
    activation_allowed: bool
    traffic_switching_allowed: bool
    evidence_state: str
    truth_boundary: str


class SQLiteTransactionConsistentFencingResourceReader:
    """Read one fencing/resource pair inside a single SQLite read transaction.

    The method intentionally returns no pair when both rows are absent and fails closed when only one row exists or when their persisted
    counters/versions disagree. This is a local SQLite consistency reference path, not a distributed snapshot API.
    """

    def __init__(self, database_path: str | Path, *, timeout_seconds: float = 5.0) -> None:
        # Reuse the existing reference adapter solely to validate the configured path,
        # pin timeout semantics, and ensure both local schemas are present.
        reference = SQLiteTransactionallyFencedProtectedResource(
            database_path,
            timeout_seconds=timeout_seconds,
        )
        self.database_path = reference.database_path
        self.timeout_seconds = reference.timeout_seconds

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self.database_path),
            timeout=self.timeout_seconds,
            isolation_level=None,
        )
        connection.execute(f"PRAGMA busy_timeout = {max(1, int(self.timeout_seconds * 1000))}")
        connection.execute("PRAGMA query_only = ON")
        return connection

    def snapshot_pair(
        self,
        resource_id: str,
        fencing_authority_id: str,
    ) -> SQLiteFencingResourceSnapshotPair | None:
        resource_id = _identity(resource_id, "resource_id")
        fencing_authority_id = _identity(fencing_authority_id, "fencing_authority_id")

        try:
            connection = self._connect()
            try:
                # Explicit BEGIN ensures both SELECTs participate in one SQLite read
                # transaction. The first read establishes the transaction snapshot.
                connection.execute("BEGIN")
                fencing_row = connection.execute(
                    "SELECT fencing_counter, version FROM morpheus_fencing_state "
                    "WHERE resource_id = ? AND fencing_authority_id = ?",
                    (resource_id, fencing_authority_id),
                ).fetchone()
                resource_row = connection.execute(
                    "SELECT resource_version, value, last_mutation_id, last_fencing_counter "
                    "FROM morpheus_protected_resource_state WHERE resource_id = ? AND fencing_authority_id = ?",
                    (resource_id, fencing_authority_id),
                ).fetchone()

                if fencing_row is None and resource_row is None:
                    connection.commit()
                    return None
                if fencing_row is None or resource_row is None:
                    raise ValueError("persisted fencing/resource pair is incomplete")

                fencing_counter = _non_negative_counter(
                    fencing_row[0],
                    "persisted fencing_counter",
                )
                fencing_version = _positive_version(
                    fencing_row[1],
                    "persisted fencing version",
                )

                resource_version = _positive_version(
                    resource_row[0],
                    "persisted resource_version",
                )
                value = resource_row[1]
                if not isinstance(value, str):
                    raise ValueError("persisted protected-resource value must be text")
                mutation_id = _identity(
                    resource_row[2],  # type: ignore[arg-type]
                    "persisted last_mutation_id",
                )
                resource_counter = _non_negative_counter(
                    resource_row[3],
                    "persisted last_fencing_counter",
                )

                if fencing_counter != resource_counter:
                    raise ValueError("persisted fencing/resource counters disagree")
                if fencing_version != resource_version:
                    raise ValueError("persisted fencing/resource versions disagree")

                fencing = AtomicFencingSnapshot(
                    resource_id,
                    fencing_authority_id,
                    fencing_counter,
                    fencing_version,
                )
                resource = SQLiteProtectedResourceSnapshot(
                    resource_id,
                    fencing_authority_id,
                    resource_version,
                    value,
                    mutation_id,
                    resource_counter,
                )
                pair = SQLiteFencingResourceSnapshotPair(
                    resource_id=resource_id,
                    fencing_authority_id=fencing_authority_id,
                    fencing=fencing,
                    resource=resource,
                    automatic_control_allowed=False,
                    activation_allowed=False,
                    traffic_switching_allowed=False,
                    evidence_state=EVIDENCE_STATE,
                    truth_boundary=TRUTH_BOUNDARY,
                )
                connection.commit()
                return pair
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()
        except ValueError:
            raise
        except sqlite3.Error as exc:
            raise ValueError("SQLite transaction-consistent fencing/resource snapshot failed") from exc
