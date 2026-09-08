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


RESOURCE_ID = "resource-schema-drift"
AUTHORITY_ID = "authority-schema-drift"


def _seed(database: Path) -> None:
    result = SQLiteTransactionallyFencedProtectedResource(database).mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        11,
        mutation_id="mutation-11",
        value="committed-11",
    )
    assert result.outcome == "applied"
    assert result.state_changed is True


def test_long_lived_reader_fails_closed_after_compatible_sqlite_schema_change(tmp_path: Path) -> None:
    database = tmp_path / "snapshot-schema-drift.sqlite3"
    _seed(database)

    reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=0.2)
    before = reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)
    assert before is not None
    assert before.fencing.fencing_counter == 11
    assert before.fencing.version == 1
    assert before.resource.resource_version == 1
    assert before.resource.last_mutation_id == "mutation-11"
    assert before.resource.value == "committed-11"

    connection = sqlite3.connect(database, timeout=0.2, isolation_level=None)
    try:
        original_schema_version = connection.execute("PRAGMA schema_version").fetchone()[0]
        connection.execute(
            "CREATE INDEX morpheus_evidence_schema_drift_idx "
            "ON morpheus_protected_resource_state(last_fencing_counter)"
        )
        changed_schema_version = connection.execute("PRAGMA schema_version").fetchone()[0]
    finally:
        connection.close()

    assert changed_schema_version > original_schema_version

    with pytest.raises(
        ValueError,
        match="SQLite snapshot database schema changed after reader construction",
    ):
        reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)

    # Failure must not leave a read transaction that blocks a subsequent writer.
    connection = sqlite3.connect(database, timeout=0.2, isolation_level=None)
    try:
        connection.execute("PRAGMA busy_timeout = 200")
        connection.execute("BEGIN IMMEDIATE")
        connection.rollback()
    finally:
        connection.close()

    # The added index is compatible with the declared MORPHEUS table contract.
    # A freshly constructed reader revalidates that contract and pins the new
    # SQLite schema version instead of silently reusing stale construction evidence.
    fresh_reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=0.2)
    after = fresh_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)
    assert after == before
    assert after.automatic_control_allowed is False
    assert after.activation_allowed is False
    assert after.traffic_switching_allowed is False


def test_schema_version_guard_is_explicitly_not_migration_or_security_evidence() -> None:
    assert "schema_version drift" in TRUTH_BOUNDARY
    assert "not semantic migration validation" in TRUTH_BOUNDARY
    assert "tamper detection" in TRUTH_BOUNDARY
    assert "security boundary" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark" in TRUTH_BOUNDARY
    assert "novelty" in TRUTH_BOUNDARY
