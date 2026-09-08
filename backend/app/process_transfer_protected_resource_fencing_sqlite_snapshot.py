from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from app.process_transfer_protected_resource_fencing_atomic import AtomicFencingSnapshot
from app.process_transfer_protected_resource_fencing_sqlite_resource import SQLiteProtectedResourceSnapshot


EVIDENCE_STATE = "SQLITE_TRANSACTION_CONSISTENT_FENCING_RESOURCE_SNAPSHOT_REFERENCE"
TRUTH_BOUNDARY = (
    "This module provides a local SQLite read-transaction reference path for observing one fencing row and its protected-resource row "
    "from the same SQLite transaction snapshot. Observation connections use SQLite read-only URI mode plus query_only hardening, and "
    "reader construction does not create the database or initialize schema. Its evidence is limited to exercised local SQLite database "
    "paths. It does not establish filesystem immutability, OS authorization, distributed snapshot isolation, serializability for unrelated "
    "databases, cross-host linearizability, external-resource consistency, network-partition safety, power-loss durability, production "
    "failover, activation authority, traffic-switching authority, HA/SLA behavior or production readiness, and makes no benchmark, "
    "performance, novelty, patentability or scientific-effect claim."
)

_REQUIRED_COLUMNS = {
    "morpheus_fencing_state": frozenset(
        {
            "resource_id",
            "fencing_authority_id",
            "fencing_counter",
            "version",
        }
    ),
    "morpheus_protected_resource_state": frozenset(
        {
            "resource_id",
            "fencing_authority_id",
            "resource_version",
            "value",
            "last_mutation_id",
            "last_fencing_counter",
        }
    ),
}
_REQUIRED_TABLES = frozenset(_REQUIRED_COLUMNS)
_REQUIRED_PRIMARY_KEY = ("resource_id", "fencing_authority_id")


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

    Construction is deliberately observation-only: the database must already exist
    with both MORPHEUS reference tables, the columns consumed by this reader, the
    expected composite identity key, and mandatory-column nullability. Connections
    are opened using SQLite read-only URI mode before query_only is enabled. The
    method returns no pair when both rows are absent and fails closed when only one
    row exists or when persisted counters/versions disagree. This remains a local
    SQLite consistency reference path, not a distributed snapshot API or an
    authorization boundary.
    """

    def __init__(self, database_path: str | Path, *, timeout_seconds: float = 5.0) -> None:
        if isinstance(database_path, bool) or not isinstance(database_path, (str, Path)):
            raise ValueError("database_path must be a filesystem path")
        candidate_path = Path(database_path)
        if not candidate_path.name:
            raise ValueError("database_path must name a database file")
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        self.database_path = candidate_path.resolve()
        self.timeout_seconds = float(timeout_seconds)
        self._database_uri = f"{self.database_path.as_uri()}?mode=ro"
        self._validate_required_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._database_uri,
            timeout=self.timeout_seconds,
            isolation_level=None,
            uri=True,
        )
        connection.execute(f"PRAGMA busy_timeout = {max(1, int(self.timeout_seconds * 1000))}")
        connection.execute("PRAGMA query_only = ON")
        return connection

    def _validate_required_schema(self) -> None:
        missing_columns: list[str] = []
        incompatible_shape: list[str] = []
        try:
            connection = self._connect()
            try:
                rows = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN (?, ?)",
                    tuple(sorted(_REQUIRED_TABLES)),
                ).fetchall()
                present = {row[0] for row in rows if isinstance(row[0], str)}
                missing_tables = sorted(_REQUIRED_TABLES - present)
                if missing_tables:
                    raise ValueError(
                        "SQLite snapshot database is missing required schema: "
                        + ", ".join(missing_tables)
                    )

                for table in sorted(_REQUIRED_TABLES):
                    column_rows = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
                    metadata = {
                        row[1]: row
                        for row in column_rows
                        if len(row) > 5 and isinstance(row[1], str)
                    }
                    present_columns = set(metadata)
                    missing = sorted(_REQUIRED_COLUMNS[table] - present_columns)
                    if missing:
                        missing_columns.append(f"{table}({', '.join(missing)})")
                        continue

                    primary_key = tuple(
                        row[1]
                        for row in sorted(
                            (row for row in column_rows if len(row) > 5 and isinstance(row[5], int) and row[5] > 0),
                            key=lambda row: row[5],
                        )
                    )
                    if primary_key != _REQUIRED_PRIMARY_KEY:
                        incompatible_shape.append(
                            f"{table}(primary key must be {', '.join(_REQUIRED_PRIMARY_KEY)})"
                        )

                    nullable = sorted(
                        column
                        for column in _REQUIRED_COLUMNS[table]
                        if metadata[column][3] != 1
                    )
                    if nullable:
                        incompatible_shape.append(
                            f"{table}(required columns must be NOT NULL: {', '.join(nullable)})"
                        )
            finally:
                connection.close()
        except ValueError:
            raise
        except sqlite3.Error as exc:
            raise ValueError("failed to open existing SQLite snapshot database read-only") from exc

        if missing_columns:
            raise ValueError(
                "SQLite snapshot database is missing required columns: "
                + "; ".join(missing_columns)
            )
        if incompatible_shape:
            raise ValueError(
                "SQLite snapshot database has incompatible required schema: "
                + "; ".join(incompatible_shape)
            )

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
