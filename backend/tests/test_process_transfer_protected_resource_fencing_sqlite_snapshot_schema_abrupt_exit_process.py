from __future__ import annotations

import multiprocessing as mp
import os
from pathlib import Path
import sqlite3

from app.process_transfer_protected_resource_fencing_sqlite_resource import (
    SQLiteTransactionallyFencedProtectedResource,
)
from app.process_transfer_protected_resource_fencing_sqlite_snapshot import (
    SQLiteTransactionConsistentFencingResourceReader,
    TRUTH_BOUNDARY,
)


RESOURCE_ID = "resource-schema-abrupt-exit-process"
AUTHORITY_ID = "authority-schema-abrupt-exit-process"
PRESERVED_TABLE = "morpheus_protected_resource_state_during_abrupt_exit"
CHILD_EXIT_CODE = 17


def _seed(database: Path) -> None:
    result = SQLiteTransactionallyFencedProtectedResource(database).mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        51,
        mutation_id="mutation-51",
        value="committed-51",
    )
    assert result.outcome == "applied"
    assert result.state_changed is True


def _stage_incompatible_replacement_then_exit(
    database: str,
    staged: mp.synchronize.Event,
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

    # Deliberately terminate without commit, rollback, connection.close(), or finally
    # cleanup. This exercises local process-exit containment only; it is not evidence
    # for power loss, kernel crashes, storage faults, or arbitrary crash recovery.
    os._exit(CHILD_EXIT_CODE)


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


def _assert_committed_schema_intact(database: Path) -> None:
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
        assert resource == (1, "committed-51", "mutation-51", 51)

        fencing = connection.execute(
            "SELECT fencing_counter, version FROM morpheus_fencing_state "
            "WHERE resource_id = ? AND fencing_authority_id = ?",
            (RESOURCE_ID, AUTHORITY_ID),
        ).fetchone()
        assert fencing == (51, 1)

        # Abrupt process exit must not leave the exercised SQLite write lock behind.
        connection.execute("PRAGMA busy_timeout = 500")
        connection.execute("BEGIN IMMEDIATE")
        connection.rollback()
    finally:
        connection.close()


def test_cross_process_uncommitted_incompatible_schema_replacement_abrupt_exit_is_contained(
    tmp_path: Path,
) -> None:
    database = tmp_path / "snapshot-schema-abrupt-exit-process.sqlite3"
    _seed(database)

    stale_reader = SQLiteTransactionConsistentFencingResourceReader(
        database, timeout_seconds=0.5
    )
    _assert_pair(
        stale_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
        counter=51,
        version=1,
        mutation_id="mutation-51",
        value="committed-51",
    )

    context = mp.get_context("spawn")
    staged = context.Event()
    child = context.Process(
        target=_stage_incompatible_replacement_then_exit,
        args=(str(database), staged),
    )
    child.start()
    assert staged.wait(2.0), "schema abrupt-exit child did not stage replacement"

    # While the incompatible DDL is uncommitted, observations must still expose only
    # the last committed coherent fencing/resource pair.
    _assert_pair(
        stale_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
        counter=51,
        version=1,
        mutation_id="mutation-51",
        value="committed-51",
    )

    child.join(timeout=5.0)
    assert not child.is_alive(), "schema abrupt-exit child did not terminate"
    assert child.exitcode == CHILD_EXIT_CODE

    # SQLite process-exit cleanup must leave the last committed schema/data intact.
    _assert_committed_schema_intact(database)

    # No schema change committed, so the previously constructed reader remains valid.
    _assert_pair(
        stale_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
        counter=51,
        version=1,
        mutation_id="mutation-51",
        value="committed-51",
    )

    # A fresh reader independently revalidates the unchanged committed schema.
    fresh_reader = SQLiteTransactionConsistentFencingResourceReader(
        database, timeout_seconds=0.5
    )
    _assert_pair(
        fresh_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
        counter=51,
        version=1,
        mutation_id="mutation-51",
        value="committed-51",
    )

    # Later normal fenced-resource progress must still be possible.
    successor = SQLiteTransactionallyFencedProtectedResource(database).mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        52,
        mutation_id="mutation-52",
        value="committed-52",
    )
    assert successor.outcome == "applied"
    assert successor.state_changed is True

    _assert_pair(
        fresh_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
        counter=52,
        version=2,
        mutation_id="mutation-52",
        value="committed-52",
    )


def test_cross_process_schema_abrupt_exit_gate_does_not_expand_truth_claims() -> None:
    assert "tamper detection" in TRUTH_BOUNDARY
    assert "security boundary" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark" in TRUTH_BOUNDARY
    assert "novelty" in TRUTH_BOUNDARY
