from __future__ import annotations

from pathlib import Path
import sqlite3
import time

import pytest

from app.process_transfer_protected_resource_fencing_sqlite_resource import (
    SQLiteTransactionallyFencedProtectedResource,
)
from app.process_transfer_protected_resource_fencing_sqlite_snapshot import (
    SQLiteTransactionConsistentFencingResourceReader,
    TRUTH_BOUNDARY,
)


RESOURCE_ID = "resource-snapshot-cleanup"
AUTHORITY_ID = "authority-snapshot-cleanup"


def _seed_valid_pair(database: Path) -> None:
    result = SQLiteTransactionallyFencedProtectedResource(database).mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        7,
        mutation_id="mutation-7",
        value="committed-7",
    )
    assert result.outcome == "applied"
    assert result.state_changed is True


def _assert_external_write_lock_available(database: Path) -> None:
    connection = sqlite3.connect(database, timeout=0.2, isolation_level=None)
    try:
        connection.execute("PRAGMA busy_timeout = 200")
        connection.execute("BEGIN IMMEDIATE")
        connection.rollback()
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("resource_id", "authority_id", "expected_fragment"),
    [
        ("", AUTHORITY_ID, "resource_id must be a non-empty string"),
        ("   ", AUTHORITY_ID, "resource_id must be a non-empty string"),
        (RESOURCE_ID, "", "fencing_authority_id must be a non-empty string"),
        (RESOURCE_ID, "\t  ", "fencing_authority_id must be a non-empty string"),
    ],
)
def test_snapshot_reader_rejects_invalid_caller_identity_without_lock_leakage(
    tmp_path: Path,
    resource_id: str,
    authority_id: str,
    expected_fragment: str,
) -> None:
    database = tmp_path / "invalid-caller-identity.sqlite3"
    _seed_valid_pair(database)
    reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=0.2)

    with pytest.raises(ValueError, match=expected_fragment):
        reader.snapshot_pair(resource_id, authority_id)

    _assert_external_write_lock_available(database)

    pair = reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)
    assert pair is not None
    assert pair.fencing.fencing_counter == 7
    assert pair.resource.value == "committed-7"
    assert pair.automatic_control_allowed is False
    assert pair.activation_allowed is False
    assert pair.traffic_switching_allowed is False


def test_persisted_domain_failure_releases_transaction_for_subsequent_writer_and_reader(tmp_path: Path) -> None:
    database = tmp_path / "domain-failure-cleanup.sqlite3"
    _seed_valid_pair(database)

    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "UPDATE morpheus_protected_resource_state SET last_mutation_id = '   ' "
            "WHERE resource_id = ? AND fencing_authority_id = ?",
            (RESOURCE_ID, AUTHORITY_ID),
        )
        connection.commit()
    finally:
        connection.close()

    reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=0.2)
    with pytest.raises(ValueError, match="persisted last_mutation_id must be a non-empty string"):
        reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)

    # A failed observation must not retain a read transaction that blocks a
    # subsequent database writer. Restore only the deliberately malformed test
    # row, then exercise the repository writer and reader normally.
    connection = sqlite3.connect(database, timeout=0.2, isolation_level=None)
    try:
        connection.execute("PRAGMA busy_timeout = 200")
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "UPDATE morpheus_protected_resource_state SET last_mutation_id = ? "
            "WHERE resource_id = ? AND fencing_authority_id = ?",
            ("mutation-7", RESOURCE_ID, AUTHORITY_ID),
        )
        connection.commit()
    finally:
        connection.close()

    mutation = SQLiteTransactionallyFencedProtectedResource(database, timeout_seconds=0.2).mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        8,
        mutation_id="mutation-8",
        value="committed-8",
    )
    assert mutation.outcome == "applied"
    assert mutation.state_changed is True

    pair = reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)
    assert pair is not None
    assert pair.fencing.fencing_counter == 8
    assert pair.fencing.version == 2
    assert pair.resource.resource_version == 2
    assert pair.resource.last_mutation_id == "mutation-8"
    assert pair.resource.value == "committed-8"


def test_repeated_failed_observations_do_not_accumulate_sqlite_locks(tmp_path: Path) -> None:
    database = tmp_path / "repeated-failure-cleanup.sqlite3"
    _seed_valid_pair(database)

    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "UPDATE morpheus_protected_resource_state SET last_mutation_id = '   ' "
            "WHERE resource_id = ? AND fencing_authority_id = ?",
            (RESOURCE_ID, AUTHORITY_ID),
        )
        connection.commit()
    finally:
        connection.close()

    reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=0.2)
    for _ in range(12):
        with pytest.raises(ValueError, match="persisted last_mutation_id must be a non-empty string"):
            reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)
        _assert_external_write_lock_available(database)

    assert "local SQLite" in TRUTH_BOUNDARY
    assert "does not establish" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark" in TRUTH_BOUNDARY


def test_snapshot_lock_contention_fails_closed_then_same_reader_recovers(tmp_path: Path) -> None:
    database = tmp_path / "snapshot-lock-contention.sqlite3"
    _seed_valid_pair(database)
    reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=0.15)

    before = reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)
    assert before is not None

    blocker = sqlite3.connect(database, timeout=0.2, isolation_level=None)
    try:
        blocker.execute("PRAGMA busy_timeout = 200")
        blocker.execute("BEGIN EXCLUSIVE")

        started = time.monotonic()
        with pytest.raises(
            ValueError,
            match="SQLite transaction-consistent fencing/resource snapshot failed",
        ):
            reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)
        elapsed = time.monotonic() - started

        # This is only a generous hang detector around a configured 150 ms
        # SQLite busy timeout. It is not a latency or performance assertion.
        assert elapsed < 2.0
    finally:
        blocker.rollback()
        blocker.close()

    after = reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)
    assert after == before
    assert after.fencing.fencing_counter == 7
    assert after.fencing.version == 1
    assert after.resource.resource_version == 1
    assert after.resource.last_mutation_id == "mutation-7"
    assert after.resource.value == "committed-7"
    assert after.automatic_control_allowed is False
    assert after.activation_allowed is False
    assert after.traffic_switching_allowed is False

    _assert_external_write_lock_available(database)
