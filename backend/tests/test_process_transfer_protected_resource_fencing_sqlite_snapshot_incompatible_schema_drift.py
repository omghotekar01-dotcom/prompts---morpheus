from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from app.process_transfer_protected_resource_fencing_sqlite_resource import (
    SQLiteTransactionallyFencedProtectedResource,
)
from app.process_transfer_protected_resource_fencing_sqlite_snapshot import (
    SQLiteTransactionConsistentFencingResourceReader,
    TRUTH_BOUNDARY,
)


RESOURCE_ID = "resource-incompatible-schema-drift"
AUTHORITY_ID = "authority-incompatible-schema-drift"


def _seed(database: Path) -> None:
    result = SQLiteTransactionallyFencedProtectedResource(database).mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        17,
        mutation_id="mutation-17",
        value="committed-17",
    )
    assert result.outcome == "applied"
    assert result.state_changed is True


def _replace_resource_table_with_incompatible_schema(database: Path) -> None:
    connection = sqlite3.connect(database, timeout=0.2, isolation_level=None)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "ALTER TABLE morpheus_protected_resource_state "
            "RENAME TO morpheus_protected_resource_state_before_incompatible_drift"
        )
        connection.execute(
            """
            CREATE TABLE morpheus_protected_resource_state (
                resource_id TEXT NOT NULL,
                fencing_authority_id TEXT NOT NULL,
                resource_version INTEGER NOT NULL,
                value TEXT NOT NULL,
                last_fencing_counter INTEGER NOT NULL,
                PRIMARY KEY (resource_id, fencing_authority_id)
            )
            """
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def test_incompatible_post_construction_schema_drift_fails_closed_without_reader_repair(tmp_path: Path) -> None:
    database = tmp_path / "snapshot-incompatible-schema-drift.sqlite3"
    _seed(database)

    reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=0.2)
    before = reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)
    assert before is not None
    assert before.fencing.fencing_counter == 17
    assert before.fencing.version == 1
    assert before.resource.resource_version == 1
    assert before.resource.last_mutation_id == "mutation-17"
    assert before.resource.value == "committed-17"
    assert before.automatic_control_allowed is False
    assert before.activation_allowed is False
    assert before.traffic_switching_allowed is False

    _replace_resource_table_with_incompatible_schema(database)
    bytes_after_external_schema_change = database.read_bytes()

    with pytest.raises(
        ValueError,
        match="SQLite snapshot database schema changed after reader construction",
    ):
        reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)

    # A fresh reader must revalidate the current schema rather than treating
    # reconstruction as recovery from an incompatible migration.
    with pytest.raises(
        ValueError,
        match="SQLite snapshot database is missing required columns:.*last_mutation_id",
    ):
        SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=0.2)

    # Both failure paths are observation-only. They must not repair or initialize
    # the incompatible target schema or otherwise rewrite this exercised DB file.
    assert database.read_bytes() == bytes_after_external_schema_change

    connection = sqlite3.connect(database, timeout=0.2, isolation_level=None)
    try:
        columns = {
            row[1]
            for row in connection.execute(
                'PRAGMA table_info("morpheus_protected_resource_state")'
            ).fetchall()
        }
        assert "last_mutation_id" not in columns

        preserved = connection.execute(
            "SELECT resource_version, value, last_mutation_id, last_fencing_counter "
            "FROM morpheus_protected_resource_state_before_incompatible_drift "
            "WHERE resource_id = ? AND fencing_authority_id = ?",
            (RESOURCE_ID, AUTHORITY_ID),
        ).fetchone()
        assert preserved == (1, "committed-17", "mutation-17", 17)

        # The rejected long-lived observation must not retain a transaction that
        # prevents an independent writer from acquiring the local SQLite write lock.
        connection.execute("PRAGMA busy_timeout = 200")
        connection.execute("BEGIN IMMEDIATE")
        connection.rollback()
    finally:
        connection.close()


def test_incompatible_schema_drift_gate_does_not_expand_truth_claims() -> None:
    assert "schema_version drift" in TRUTH_BOUNDARY
    assert "not semantic migration validation" in TRUTH_BOUNDARY
    assert "tamper detection" in TRUTH_BOUNDARY
    assert "security boundary" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark" in TRUTH_BOUNDARY
    assert "novelty" in TRUTH_BOUNDARY
