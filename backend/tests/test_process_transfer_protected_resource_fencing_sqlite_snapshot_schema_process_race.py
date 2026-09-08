from __future__ import annotations

import multiprocessing as mp
from pathlib import Path
import sqlite3
from threading import Event

import pytest

from app.process_transfer_protected_resource_fencing_sqlite_resource import (
    SQLiteTransactionallyFencedProtectedResource,
)
from app.process_transfer_protected_resource_fencing_sqlite_snapshot import (
    SQLiteTransactionConsistentFencingResourceReader,
)


RESOURCE_ID = "resource-schema-process-race"
AUTHORITY_ID = "authority-schema-process-race"


def _seed(database: Path) -> None:
    result = SQLiteTransactionallyFencedProtectedResource(database).mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        29,
        mutation_id="mutation-29",
        value="committed-29",
    )
    assert result.outcome == "applied"
    assert result.state_changed is True


def _persisted_rows(database: Path) -> tuple[tuple[object, ...], tuple[object, ...]]:
    connection = sqlite3.connect(database, timeout=1.0, isolation_level=None)
    try:
        fencing = connection.execute(
            "SELECT fencing_counter, version FROM morpheus_fencing_state "
            "WHERE resource_id = ? AND fencing_authority_id = ?",
            (RESOURCE_ID, AUTHORITY_ID),
        ).fetchone()
        resource = connection.execute(
            "SELECT resource_version, value, last_mutation_id, last_fencing_counter "
            "FROM morpheus_protected_resource_state "
            "WHERE resource_id = ? AND fencing_authority_id = ?",
            (RESOURCE_ID, AUTHORITY_ID),
        ).fetchone()
    finally:
        connection.close()

    assert fencing is not None
    assert resource is not None
    return tuple(fencing), tuple(resource)


def _schema_writer_process(
    database: str,
    index_name: str,
    started: mp.synchronize.Event,
    result_queue: mp.queues.Queue,
) -> None:
    connection = sqlite3.connect(database, timeout=2.0, isolation_level=None)
    try:
        connection.execute("PRAGMA busy_timeout = 2000")
        started.set()
        connection.execute(
            f'CREATE INDEX "{index_name}" '
            "ON morpheus_protected_resource_state(last_fencing_counter)"
        )
        result_queue.put(("ok", None))
    except BaseException as exc:  # pragma: no cover - child error is asserted in parent
        result_queue.put(("error", repr(exc)))
        raise
    finally:
        connection.close()


class _FetchOneGate:
    def __init__(self, cursor: sqlite3.Cursor, reached: Event, release: Event) -> None:
        self._cursor = cursor
        self._reached = reached
        self._release = release

    def fetchone(self):  # type: ignore[no-untyped-def]
        row = self._cursor.fetchone()
        self._reached.set()
        if not self._release.wait(3.0):
            raise AssertionError("cross-process schema-race synchronization timed out")
        return row

    def __getattr__(self, name: str):  # type: ignore[no-untyped-def]
        return getattr(self._cursor, name)


class _ConnectionGate:
    def __init__(self, connection: sqlite3.Connection, reached: Event, release: Event) -> None:
        self._connection = connection
        self._reached = reached
        self._release = release

    def execute(self, sql: str, *args, **kwargs):  # type: ignore[no-untyped-def]
        cursor = self._connection.execute(sql, *args, **kwargs)
        if " ".join(sql.split()).upper() == "PRAGMA SCHEMA_VERSION":
            return _FetchOneGate(cursor, self._reached, self._release)
        return cursor

    def __getattr__(self, name: str):  # type: ignore[no-untyped-def]
        return getattr(self._connection, name)


def _gate_after_schema_snapshot(
    reader: SQLiteTransactionConsistentFencingResourceReader,
    reached: Event,
    release: Event,
) -> None:
    original_connect = reader._connect

    def gated_connect():  # type: ignore[no-untyped-def]
        return _ConnectionGate(original_connect(), reached, release)

    reader._connect = gated_connect  # type: ignore[method-assign]


def _assert_coherent_pair(pair) -> None:  # type: ignore[no-untyped-def]
    assert pair is not None
    assert pair.fencing.fencing_counter == 29
    assert pair.fencing.version == 1
    assert pair.resource.last_fencing_counter == 29
    assert pair.resource.resource_version == 1
    assert pair.resource.last_mutation_id == "mutation-29"
    assert pair.resource.value == "committed-29"
    assert pair.fencing.fencing_counter == pair.resource.last_fencing_counter
    assert pair.fencing.version == pair.resource.resource_version
    assert pair.automatic_control_allowed is False
    assert pair.activation_allowed is False
    assert pair.traffic_switching_allowed is False


def _assert_writer_available(database: Path) -> None:
    connection = sqlite3.connect(database, timeout=0.5, isolation_level=None)
    try:
        connection.execute("PRAGMA busy_timeout = 500")
        connection.execute("BEGIN IMMEDIATE")
        connection.rollback()
    finally:
        connection.close()


def _join_child(process: mp.Process, queue: mp.queues.Queue) -> None:
    process.join(timeout=4.0)
    assert not process.is_alive(), "schema writer child process did not complete"
    assert process.exitcode == 0
    status, detail = queue.get(timeout=1.0)
    assert status == "ok", detail


def test_cross_process_schema_change_waiting_behind_pinned_read_keeps_coherent_pair(
    tmp_path: Path,
) -> None:
    database = tmp_path / "snapshot-schema-process-read-first.sqlite3"
    _seed(database)
    rows_before = _persisted_rows(database)

    reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=1.0)
    reached = Event()
    release = Event()
    _gate_after_schema_snapshot(reader, reached, release)

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        read_future = pool.submit(reader.snapshot_pair, RESOURCE_ID, AUTHORITY_ID)
        assert reached.wait(1.0), "reader did not pin its SQLite schema/read snapshot"

        context = mp.get_context("spawn")
        started = context.Event()
        queue = context.Queue()
        child = context.Process(
            target=_schema_writer_process,
            args=(str(database), "morpheus_schema_process_read_first_idx", started, queue),
        )
        child.start()
        assert started.wait(2.0), "schema writer child did not enter the race"

        release.set()
        pair = read_future.result(timeout=3.0)
        _join_child(child, queue)

    _assert_coherent_pair(pair)
    assert _persisted_rows(database) == rows_before
    _assert_writer_available(database)

    fresh = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=0.5)
    _assert_coherent_pair(fresh.snapshot_pair(RESOURCE_ID, AUTHORITY_ID))


def test_cross_process_schema_change_committed_before_stale_reader_fails_closed(
    tmp_path: Path,
) -> None:
    database = tmp_path / "snapshot-schema-process-schema-first.sqlite3"
    _seed(database)
    rows_before = _persisted_rows(database)

    stale_reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=1.0)

    context = mp.get_context("spawn")
    started = context.Event()
    queue = context.Queue()
    child = context.Process(
        target=_schema_writer_process,
        args=(str(database), "morpheus_schema_process_schema_first_idx", started, queue),
    )
    child.start()
    assert started.wait(2.0), "schema writer child did not start"
    _join_child(child, queue)

    with pytest.raises(
        ValueError,
        match="SQLite snapshot database schema changed after reader construction",
    ):
        stale_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)

    assert _persisted_rows(database) == rows_before
    _assert_writer_available(database)

    fresh = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=0.5)
    _assert_coherent_pair(fresh.snapshot_pair(RESOURCE_ID, AUTHORITY_ID))
