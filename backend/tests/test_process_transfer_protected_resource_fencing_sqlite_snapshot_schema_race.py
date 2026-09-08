from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
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


RESOURCE_ID = "resource-schema-race"
AUTHORITY_ID = "authority-schema-race"


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


def _create_compatible_index(database: Path, index_name: str, started: Event | None = None) -> None:
    connection = sqlite3.connect(database, timeout=1.0, isolation_level=None)
    try:
        connection.execute("PRAGMA busy_timeout = 1000")
        if started is not None:
            started.set()
        connection.execute(
            f'CREATE INDEX "{index_name}" '
            "ON morpheus_protected_resource_state(last_fencing_counter)"
        )
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
        if not self._release.wait(2.0):
            raise AssertionError("schema-race test synchronization timed out")
        return row

    def __getattr__(self, name: str):  # type: ignore[no-untyped-def]
        return getattr(self._cursor, name)


class _ConnectionGate:
    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        reached: Event,
        release: Event,
        before_begin: bool = False,
        after_schema_fetch: bool = False,
    ) -> None:
        self._connection = connection
        self._reached = reached
        self._release = release
        self._before_begin = before_begin
        self._after_schema_fetch = after_schema_fetch

    def execute(self, sql: str, *args, **kwargs):  # type: ignore[no-untyped-def]
        normalized = " ".join(sql.split()).upper()
        if self._before_begin and normalized == "BEGIN":
            self._reached.set()
            if not self._release.wait(2.0):
                raise AssertionError("schema-race test synchronization timed out")

        cursor = self._connection.execute(sql, *args, **kwargs)
        if self._after_schema_fetch and normalized == "PRAGMA SCHEMA_VERSION":
            return _FetchOneGate(cursor, self._reached, self._release)
        return cursor

    def __getattr__(self, name: str):  # type: ignore[no-untyped-def]
        return getattr(self._connection, name)


def _gate_reader_connection(
    reader: SQLiteTransactionConsistentFencingResourceReader,
    *,
    reached: Event,
    release: Event,
    before_begin: bool = False,
    after_schema_fetch: bool = False,
) -> None:
    original_connect = reader._connect

    def gated_connect():  # type: ignore[no-untyped-def]
        return _ConnectionGate(
            original_connect(),
            reached=reached,
            release=release,
            before_begin=before_begin,
            after_schema_fetch=after_schema_fetch,
        )

    reader._connect = gated_connect  # type: ignore[method-assign]


def _assert_coherent_pair(pair) -> None:  # type: ignore[no-untyped-def]
    assert pair is not None
    assert pair.fencing.fencing_counter == 17
    assert pair.fencing.version == 1
    assert pair.resource.last_fencing_counter == 17
    assert pair.resource.resource_version == 1
    assert pair.resource.last_mutation_id == "mutation-17"
    assert pair.resource.value == "committed-17"
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


def test_read_transaction_that_precedes_compatible_schema_drift_returns_one_coherent_pair(
    tmp_path: Path,
) -> None:
    database = tmp_path / "snapshot-schema-race-read-first.sqlite3"
    _seed(database)
    rows_before = _persisted_rows(database)

    reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=1.0)
    reached = Event()
    release = Event()
    writer_started = Event()
    _gate_reader_connection(
        reader,
        reached=reached,
        release=release,
        after_schema_fetch=True,
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        read_future = pool.submit(reader.snapshot_pair, RESOURCE_ID, AUTHORITY_ID)
        assert reached.wait(1.0), "reader did not establish its SQLite read snapshot"

        write_future = pool.submit(
            _create_compatible_index,
            database,
            "morpheus_schema_race_read_first_idx",
            writer_started,
        )
        assert writer_started.wait(1.0), "schema writer did not enter the bounded race"

        # This releases only the test gate. SQLite decides lock ordering. Because the
        # schema-version fetch already occurred inside the reader transaction, the
        # completed observation must remain one coherent pre-drift snapshot.
        release.set()
        pair = read_future.result(timeout=2.0)
        # Windows CI can defer completion of the DDL worker after SQLite has resolved
        # the lock ordering. Keep this as a generous hang detector rather than a
        # scheduler-sensitive performance assertion; SQLite's own busy timeout remains
        # bounded at one second.
        write_future.result(timeout=10.0)

    _assert_coherent_pair(pair)
    assert _persisted_rows(database) == rows_before
    _assert_writer_available(database)

    fresh = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=0.5)
    _assert_coherent_pair(fresh.snapshot_pair(RESOURCE_ID, AUTHORITY_ID))


def test_compatible_schema_drift_that_commits_before_read_transaction_fails_closed(
    tmp_path: Path,
) -> None:
    database = tmp_path / "snapshot-schema-race-schema-first.sqlite3"
    _seed(database)
    rows_before = _persisted_rows(database)

    reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=1.0)
    reached = Event()
    release = Event()
    _gate_reader_connection(
        reader,
        reached=reached,
        release=release,
        before_begin=True,
    )

    with ThreadPoolExecutor(max_workers=1) as pool:
        read_future = pool.submit(reader.snapshot_pair, RESOURCE_ID, AUTHORITY_ID)
        assert reached.wait(1.0), "reader did not enter the bounded schema/read race"

        # The reader invocation is already in flight, but its explicit read transaction
        # has not begun. A compatible schema change can therefore commit first. Once
        # released, the stale reader must observe the changed schema_version and reject.
        _create_compatible_index(database, "morpheus_schema_race_schema_first_idx")
        release.set()

        with pytest.raises(
            ValueError,
            match="SQLite snapshot database schema changed after reader construction",
        ):
            read_future.result(timeout=2.0)

    assert _persisted_rows(database) == rows_before
    _assert_writer_available(database)

    # The schema change itself is compatible. Reconstruction is allowed only through
    # a fresh reader that revalidates the current contract and pins the new version.
    fresh = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=0.5)
    _assert_coherent_pair(fresh.snapshot_pair(RESOURCE_ID, AUTHORITY_ID))
