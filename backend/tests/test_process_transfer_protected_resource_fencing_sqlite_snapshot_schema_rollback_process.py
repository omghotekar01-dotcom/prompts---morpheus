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


RESOURCE_ID = "resource-schema-rollback-process"
AUTHORITY_ID = "authority-schema-rollback-process"
PRESERVED_TABLE = "morpheus_protected_resource_state_during_uncommitted_replacement"


def _seed(database: Path) -> None:
    result = SQLiteTransactionallyFencedProtectedResource(database).mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        41,
        mutation_id="mutation-41",
        value="committed-41",
    )
    assert result.outcome == "applied"
    assert result.state_changed is True


def _stage_incompatible_replacement_then_rollback(
    database: str,
    staged: mp.synchronize.Event,
    release: mp.synchronize.Event,
    result_queue: mp.queues.Queue,
) -> None:
    connection = sqlite3.connect(database, timeout=2.0, isolation_level=None)
    try:
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
        if not release.wait(3.0):
            raise RuntimeError("parent did not release staged schema transaction")

        # Deliberately fail after the incompatible replacement has been staged.
        raise RuntimeError("deliberate pre-commit schema replacement failure")
    except RuntimeError as exc:
        connection.rollback()
        result_queue.put(("rolled_back", str(exc)))
    except BaseException as exc:  # pragma: no cover - child error asserted in parent
        connection.rollback()
        result_queue.put(("error", repr(exc)))
        raise
    finally:
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
        assert resource == (1, "committed-41", "mutation-41", 41)

        fencing = connection.execute(
            "SELECT fencing_counter, version FROM morpheus_fencing_state "
            "WHERE resource_id = ? AND fencing_authority_id = ?",
            (RESOURCE_ID, AUTHORITY_ID),
        ).fetchone()
        assert fencing == (41, 1)

        # A later independent writer must be able to acquire the database write lock.
        connection.execute("PRAGMA busy_timeout = 500")
        connection.execute("BEGIN IMMEDIATE")
        connection.rollback()
    finally:
        connection.close()


def test_cross_process_uncommitted_incompatible_schema_replacement_is_contained(
    tmp_path: Path,
) -> None:
    database = tmp_path / "snapshot-schema-rollback-process.sqlite3"
    _seed(database)

    stale_reader = SQLiteTransactionConsistentFencingResourceReader(
        database, timeout_seconds=0.5
    )
    _assert_pair(
        stale_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
        counter=41,
        version=1,
        mutation_id="mutation-41",
        value="committed-41",
    )

    context = mp.get_context("spawn")
    staged = context.Event()
    release = context.Event()
    queue = context.Queue()
    child = context.Process(
        target=_stage_incompatible_replacement_then_rollback,
        args=(str(database), staged, release, queue),
    )
    child.start()
    assert staged.wait(2.0), "schema rollback child did not stage replacement"

    # The child's incompatible schema exists only inside its uncommitted transaction.
    # An independent observation must continue to see the last committed coherent pair.
    _assert_pair(
        stale_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
        counter=41,
        version=1,
        mutation_id="mutation-41",
        value="committed-41",
    )

    release.set()
    child.join(timeout=5.0)
    assert not child.is_alive(), "schema rollback child did not complete"
    assert child.exitcode == 0
    status, detail = queue.get(timeout=1.0)
    assert status == "rolled_back", detail
    assert "deliberate pre-commit schema replacement failure" in detail

    # Rollback must restore the original committed schema and data, not a mixture.
    _assert_committed_schema_intact(database)

    # The existing reader remains valid because no schema change committed.
    _assert_pair(
        stale_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
        counter=41,
        version=1,
        mutation_id="mutation-41",
        value="committed-41",
    )

    # A fresh reader must independently validate the unchanged committed schema.
    fresh_reader = SQLiteTransactionConsistentFencingResourceReader(
        database, timeout_seconds=0.5
    )
    _assert_pair(
        fresh_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
        counter=41,
        version=1,
        mutation_id="mutation-41",
        value="committed-41",
    )

    # Later normal mutation remains possible after the child has rolled back and exited.
    successor = SQLiteTransactionallyFencedProtectedResource(database).mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        42,
        mutation_id="mutation-42",
        value="committed-42",
    )
    assert successor.outcome == "applied"
    assert successor.state_changed is True

    _assert_pair(
        fresh_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
        counter=42,
        version=2,
        mutation_id="mutation-42",
        value="committed-42",
    )


def test_cross_process_schema_rollback_gate_does_not_expand_truth_claims() -> None:
    assert "not semantic migration validation" in TRUTH_BOUNDARY
    assert "tamper detection" in TRUTH_BOUNDARY
    assert "security boundary" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark" in TRUTH_BOUNDARY
    assert "novelty" in TRUTH_BOUNDARY
