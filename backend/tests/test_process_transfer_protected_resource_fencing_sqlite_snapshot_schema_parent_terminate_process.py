from __future__ import annotations

import multiprocessing as mp
from pathlib import Path
import sqlite3

from app.process_transfer_protected_resource_fencing_sqlite_resource import (
    SQLiteTransactionallyFencedProtectedResource,
)
from app.process_transfer_protected_resource_fencing_sqlite_snapshot import (
    SQLiteTransactionConsistentFencingResourceReader,
    TRUTH_BOUNDARY,
)


RESOURCE_ID = "resource-schema-parent-terminate-process"
AUTHORITY_ID = "authority-schema-parent-terminate-process"
PRESERVED_TABLE = "morpheus_protected_resource_state_during_parent_terminate"


def _seed(database: Path) -> None:
    result = SQLiteTransactionallyFencedProtectedResource(database).mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        61,
        mutation_id="mutation-61",
        value="committed-61",
    )
    assert result.outcome == "applied"
    assert result.state_changed is True


def _stage_incompatible_replacement_and_wait(
    database: str,
    staged: mp.synchronize.Event,
    release: mp.synchronize.Event,
) -> None:
    connection = sqlite3.connect(database, timeout=2.0, isolation_level=None)
    connection.execute("PRAGMA busy_timeout = 2000")
    connection.execute("BEGIN IMMEDIATE")
    connection.execute(
        "ALTER TABLE morpheus_protected_resource_state "
        f"RENAME TO {PRESERVED_TABLE}"
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
    staged.set()

    # The normal path deliberately waits without commit/rollback. The parent test
    # terminates this process externally. The release event exists only so a failed
    # parent assertion can still allow a bounded normal cleanup path in test teardown.
    try:
        release.wait(30.0)
    finally:
        if connection.in_transaction:
            connection.rollback()
        connection.close()


def _assert_pair(pair, *, counter: int, version: int, mutation_id: str, value: str) -> None:  # type: ignore[no-untyped-def]
    assert pair is not None
    assert pair.fencing.fencing_counter == counter
    assert pair.fencing.version == version
    assert pair.resource.resource_version == version
    assert pair.resource.last_mutation_id == mutation_id
    assert pair.resource.last_fencing_counter == counter
    assert pair.resource.value == value
    assert pair.fencing.fencing_counter == pair.resource.last_fencing_counter
    assert pair.fencing.version == pair.resource.resource_version
    assert pair.automatic_control_allowed is False
    assert pair.activation_allowed is False
    assert pair.traffic_switching_allowed is False


def _assert_committed_schema_and_state(database: Path) -> None:
    connection = sqlite3.connect(database, timeout=0.5, isolation_level=None)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert "morpheus_protected_resource_state" in tables
        assert PRESERVED_TABLE not in tables

        columns = {
            row[1]
            for row in connection.execute(
                'PRAGMA table_info("morpheus_protected_resource_state")'
            ).fetchall()
        }
        assert "last_mutation_id" in columns

        resource = connection.execute(
            "SELECT resource_version, value, last_mutation_id, last_fencing_counter "
            "FROM morpheus_protected_resource_state "
            "WHERE resource_id = ? AND fencing_authority_id = ?",
            (RESOURCE_ID, AUTHORITY_ID),
        ).fetchone()
        assert resource == (1, "committed-61", "mutation-61", 61)

        fencing = connection.execute(
            "SELECT fencing_counter, version FROM morpheus_fencing_state "
            "WHERE resource_id = ? AND fencing_authority_id = ?",
            (RESOURCE_ID, AUTHORITY_ID),
        ).fetchone()
        assert fencing == (61, 1)

        connection.execute("PRAGMA busy_timeout = 500")
        connection.execute("BEGIN IMMEDIATE")
        connection.rollback()
    finally:
        connection.close()


def test_parent_terminate_contains_uncommitted_incompatible_schema_replacement(
    tmp_path: Path,
) -> None:
    database = tmp_path / "snapshot-schema-parent-terminate-process.sqlite3"
    _seed(database)

    stale_reader = SQLiteTransactionConsistentFencingResourceReader(
        database, timeout_seconds=0.5
    )
    _assert_pair(
        stale_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
        counter=61,
        version=1,
        mutation_id="mutation-61",
        value="committed-61",
    )

    context = mp.get_context("spawn")
    staged = context.Event()
    release = context.Event()
    child = context.Process(
        target=_stage_incompatible_replacement_and_wait,
        args=(str(database), staged, release),
    )
    child.start()
    try:
        assert staged.wait(3.0), "schema parent-terminate child did not stage replacement"

        # The child's uncommitted incompatible DDL must remain invisible to the
        # already-constructed reader while the child still owns its write transaction.
        _assert_pair(
            stale_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
            counter=61,
            version=1,
            mutation_id="mutation-61",
            value="committed-61",
        )

        # Terminate from the parent rather than allowing child application code to
        # choose commit, rollback, close, or os._exit(). Exact termination semantics
        # are platform/runtime specific and are intentionally not generalized here.
        child.terminate()
        child.join(timeout=5.0)
        assert not child.is_alive(), "schema parent-terminate child did not terminate"
        assert child.exitcode is not None
    finally:
        if child.is_alive():
            release.set()
            child.join(timeout=2.0)
        if child.is_alive():
            child.terminate()
            child.join(timeout=2.0)

    _assert_committed_schema_and_state(database)

    # No schema change committed, so both stale and fresh readers must still expose
    # exactly the last committed coherent pair.
    _assert_pair(
        stale_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
        counter=61,
        version=1,
        mutation_id="mutation-61",
        value="committed-61",
    )
    fresh_reader = SQLiteTransactionConsistentFencingResourceReader(
        database, timeout_seconds=0.5
    )
    _assert_pair(
        fresh_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
        counter=61,
        version=1,
        mutation_id="mutation-61",
        value="committed-61",
    )

    successor = SQLiteTransactionallyFencedProtectedResource(database).mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        62,
        mutation_id="mutation-62",
        value="committed-62",
    )
    assert successor.outcome == "applied"
    assert successor.state_changed is True

    _assert_pair(
        fresh_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
        counter=62,
        version=2,
        mutation_id="mutation-62",
        value="committed-62",
    )


def test_parent_terminate_gate_does_not_expand_truth_claims() -> None:
    assert "power-loss durability" in TRUTH_BOUNDARY
    assert "security boundary" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark" in TRUTH_BOUNDARY
    assert "novelty" in TRUTH_BOUNDARY
