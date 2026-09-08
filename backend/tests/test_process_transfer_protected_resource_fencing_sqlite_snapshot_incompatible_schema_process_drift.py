from __future__ import annotations

import multiprocessing as mp
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


RESOURCE_ID = "resource-incompatible-schema-process-drift"
AUTHORITY_ID = "authority-incompatible-schema-process-drift"
PRESERVED_TABLE = "morpheus_protected_resource_state_before_process_incompatible_drift"


def _seed(database: Path) -> None:
    result = SQLiteTransactionallyFencedProtectedResource(database).mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        31,
        mutation_id="mutation-31",
        value="committed-31",
    )
    assert result.outcome == "applied"
    assert result.state_changed is True


def _replace_resource_table_process(
    database: str,
    started: mp.synchronize.Event,
    result_queue: mp.queues.Queue,
) -> None:
    connection = sqlite3.connect(database, timeout=2.0, isolation_level=None)
    try:
        connection.execute("PRAGMA busy_timeout = 2000")
        started.set()
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
        connection.commit()
        result_queue.put(("ok", None))
    except BaseException as exc:  # pragma: no cover - child error asserted in parent
        connection.rollback()
        result_queue.put(("error", repr(exc)))
        raise
    finally:
        connection.close()


def _join_child(process: mp.Process, queue: mp.queues.Queue) -> None:
    process.join(timeout=5.0)
    assert not process.is_alive(), "incompatible schema child process did not complete"
    assert process.exitcode == 0
    status, detail = queue.get(timeout=1.0)
    assert status == "ok", detail


def _assert_valid_pair(pair) -> None:  # type: ignore[no-untyped-def]
    assert pair is not None
    assert pair.fencing.fencing_counter == 31
    assert pair.fencing.version == 1
    assert pair.resource.resource_version == 1
    assert pair.resource.last_mutation_id == "mutation-31"
    assert pair.resource.last_fencing_counter == 31
    assert pair.resource.value == "committed-31"
    assert pair.fencing.fencing_counter == pair.resource.last_fencing_counter
    assert pair.fencing.version == pair.resource.resource_version
    assert pair.automatic_control_allowed is False
    assert pair.activation_allowed is False
    assert pair.traffic_switching_allowed is False


def _assert_post_child_state_and_writer_release(database: Path) -> None:
    connection = sqlite3.connect(database, timeout=0.5, isolation_level=None)
    try:
        current_columns = {
            row[1]
            for row in connection.execute(
                'PRAGMA table_info("morpheus_protected_resource_state")'
            ).fetchall()
        }
        assert "last_mutation_id" not in current_columns

        preserved = connection.execute(
            f"SELECT resource_version, value, last_mutation_id, last_fencing_counter "
            f"FROM {PRESERVED_TABLE} "
            "WHERE resource_id = ? AND fencing_authority_id = ?",
            (RESOURCE_ID, AUTHORITY_ID),
        ).fetchone()
        assert preserved == (1, "committed-31", "mutation-31", 31)

        fencing = connection.execute(
            "SELECT fencing_counter, version FROM morpheus_fencing_state "
            "WHERE resource_id = ? AND fencing_authority_id = ?",
            (RESOURCE_ID, AUTHORITY_ID),
        ).fetchone()
        assert fencing == (31, 1)

        connection.execute("PRAGMA busy_timeout = 500")
        connection.execute("BEGIN IMMEDIATE")
        connection.rollback()
    finally:
        connection.close()


def test_cross_process_incompatible_schema_drift_fails_closed_and_fresh_reader_revalidates(
    tmp_path: Path,
) -> None:
    database = tmp_path / "snapshot-incompatible-schema-process-drift.sqlite3"
    _seed(database)

    stale_reader = SQLiteTransactionConsistentFencingResourceReader(
        database, timeout_seconds=0.5
    )
    _assert_valid_pair(stale_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID))

    context = mp.get_context("spawn")
    started = context.Event()
    queue = context.Queue()
    child = context.Process(
        target=_replace_resource_table_process,
        args=(str(database), started, queue),
    )
    child.start()
    assert started.wait(2.0), "incompatible schema child process did not start"
    _join_child(child, queue)

    bytes_after_child_commit = database.read_bytes()

    with pytest.raises(
        ValueError,
        match="SQLite snapshot database schema changed after reader construction",
    ):
        stale_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)

    with pytest.raises(
        ValueError,
        match="SQLite snapshot database is missing required columns:.*last_mutation_id",
    ):
        SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=0.5)

    # Both observation failure paths must remain non-repairing/non-initializing.
    assert database.read_bytes() == bytes_after_child_commit
    _assert_post_child_state_and_writer_release(database)


def test_cross_process_incompatible_schema_gate_does_not_expand_truth_claims() -> None:
    assert "schema_version drift" in TRUTH_BOUNDARY
    assert "not semantic migration validation" in TRUTH_BOUNDARY
    assert "tamper detection" in TRUTH_BOUNDARY
    assert "security boundary" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark" in TRUTH_BOUNDARY
    assert "novelty" in TRUTH_BOUNDARY
