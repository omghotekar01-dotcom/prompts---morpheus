from __future__ import annotations

import multiprocessing as mp
from pathlib import Path
import sqlite3
from typing import Any

import pytest

from app.process_transfer_protected_resource_fencing_sqlite_resource import (
    SQLiteTransactionallyFencedProtectedResource,
)
from app.process_transfer_protected_resource_fencing_sqlite_snapshot import (
    SQLiteTransactionConsistentFencingResourceReader,
)


TRUTH_BOUNDARY = (
    "These tests provide local-host SQLite transactional-read coherence evidence only. "
    "They do not establish distributed snapshot isolation, cross-host linearizability, serializability for unrelated databases, "
    "external-resource consistency, lock-free progress, production failover, HA/SLA behavior, or production readiness."
)


def _snapshot_reader_worker(
    database_path: str,
    *,
    start_event: Any,
    result_pipe: Any,
    read_count: int,
) -> None:
    reader = SQLiteTransactionConsistentFencingResourceReader(database_path)
    if not start_event.wait(timeout=15):
        result_pipe.send(("worker_error", "start_timeout"))
        result_pipe.close()
        return

    observations: list[tuple[int, int, int, int, str, str, bool, bool, bool]] = []
    try:
        for _ in range(read_count):
            pair = reader.snapshot_pair("resource-a", "authority-a")
            if pair is None:
                result_pipe.send(("worker_error", "unexpected_absent_pair"))
                result_pipe.close()
                return
            observations.append(
                (
                    pair.fencing.fencing_counter,
                    pair.fencing.version,
                    pair.resource.last_fencing_counter,
                    pair.resource.resource_version,
                    pair.resource.value,
                    pair.resource.last_mutation_id,
                    pair.automatic_control_allowed,
                    pair.activation_allowed,
                    pair.traffic_switching_allowed,
                )
            )
        result_pipe.send(("ok", observations))
    except Exception as exc:  # pragma: no cover - cross-process evidence diagnostics.
        result_pipe.send(("worker_error", type(exc).__name__))
    finally:
        result_pipe.close()


def _successor_writer_worker(
    database_path: str,
    *,
    start_event: Any,
    result_pipe: Any,
    last_counter: int,
) -> None:
    resource = SQLiteTransactionallyFencedProtectedResource(database_path)
    if not start_event.wait(timeout=15):
        result_pipe.send(("worker_error", "start_timeout"))
        result_pipe.close()
        return

    try:
        outcomes: list[tuple[int, str, bool, bool]] = []
        for counter in range(2, last_counter + 1):
            result = resource.mutate(
                "resource-a",
                "authority-a",
                counter,
                mutation_id=f"m-{counter}",
                value=f"v-{counter}",
            )
            outcomes.append((counter, result.outcome, result.accepted, result.state_changed))
        result_pipe.send(("ok", outcomes))
    except Exception as exc:  # pragma: no cover - cross-process evidence diagnostics.
        result_pipe.send(("worker_error", type(exc).__name__))
    finally:
        result_pipe.close()


def _assert_pair_matches_committed_generation(pair: Any) -> None:
    assert pair.fencing.fencing_counter == pair.resource.last_fencing_counter
    assert pair.fencing.version == pair.resource.resource_version
    counter = pair.fencing.fencing_counter
    assert pair.resource.value == f"v-{counter}"
    assert pair.resource.last_mutation_id == f"m-{counter}"
    assert pair.automatic_control_allowed is False
    assert pair.activation_allowed is False
    assert pair.traffic_switching_allowed is False


def test_transactional_snapshot_returns_absent_or_coherent_committed_pair(tmp_path: Path) -> None:
    database = tmp_path / "fencing.sqlite3"
    resource = SQLiteTransactionallyFencedProtectedResource(database)
    reader = SQLiteTransactionConsistentFencingResourceReader(database)
    assert reader.snapshot_pair("resource-a", "authority-a") is None

    applied = resource.mutate(
        "resource-a",
        "authority-a",
        1,
        mutation_id="m-1",
        value="v-1",
    )
    assert applied.outcome == "applied"

    pair = reader.snapshot_pair("resource-a", "authority-a")
    assert pair is not None
    _assert_pair_matches_committed_generation(pair)
    assert pair.evidence_state == "SQLITE_TRANSACTION_CONSISTENT_FENCING_RESOURCE_SNAPSHOT_REFERENCE"
    assert "local SQLite read-transaction reference path" in pair.truth_boundary


def test_transactional_snapshot_fails_closed_for_incomplete_or_inconsistent_persisted_pair(tmp_path: Path) -> None:
    database = tmp_path / "fencing.sqlite3"
    resource = SQLiteTransactionallyFencedProtectedResource(database)
    resource.mutate("resource-a", "authority-a", 1, mutation_id="m-1", value="v-1")
    reader = SQLiteTransactionConsistentFencingResourceReader(database)

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE morpheus_protected_resource_state SET resource_version = 2 "
            "WHERE resource_id = 'resource-a' AND fencing_authority_id = 'authority-a'"
        )
    with pytest.raises(ValueError, match="versions disagree"):
        reader.snapshot_pair("resource-a", "authority-a")

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE morpheus_protected_resource_state SET resource_version = 1, last_fencing_counter = 2 "
            "WHERE resource_id = 'resource-a' AND fencing_authority_id = 'authority-a'"
        )
    with pytest.raises(ValueError, match="counters disagree"):
        reader.snapshot_pair("resource-a", "authority-a")

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE morpheus_protected_resource_state SET last_fencing_counter = 1 "
            "WHERE resource_id = 'resource-a' AND fencing_authority_id = 'authority-a'"
        )
        connection.execute(
            "DELETE FROM morpheus_protected_resource_state "
            "WHERE resource_id = 'resource-a' AND fencing_authority_id = 'authority-a'"
        )
    with pytest.raises(ValueError, match="pair is incomplete"):
        reader.snapshot_pair("resource-a", "authority-a")


def test_spawned_readers_never_report_torn_fencing_resource_pair_during_successor_writes(tmp_path: Path) -> None:
    ctx = mp.get_context("spawn")
    database = str(tmp_path / "fencing.sqlite3")
    resource = SQLiteTransactionallyFencedProtectedResource(database)
    first = resource.mutate("resource-a", "authority-a", 1, mutation_id="m-1", value="v-1")
    assert first.outcome == "applied"

    start_event = ctx.Event()
    processes: list[mp.Process] = []
    receivers: list[tuple[str, Any]] = []

    for reader_index in range(2):
        parent_result, child_result = ctx.Pipe(duplex=False)
        process = ctx.Process(
            target=_snapshot_reader_worker,
            kwargs={
                "database_path": database,
                "start_event": start_event,
                "result_pipe": child_result,
                "read_count": 80,
            },
        )
        process.start()
        child_result.close()
        processes.append(process)
        receivers.append((f"reader-{reader_index}", parent_result))

    parent_writer, child_writer = ctx.Pipe(duplex=False)
    writer = ctx.Process(
        target=_successor_writer_worker,
        kwargs={
            "database_path": database,
            "start_event": start_event,
            "result_pipe": child_writer,
            "last_counter": 20,
        },
    )
    writer.start()
    child_writer.close()
    processes.append(writer)
    receivers.append(("writer", parent_writer))

    start_event.set()

    reported: dict[str, Any] = {}
    for label, receiver in receivers:
        assert receiver.poll(30), f"{label} did not report transactional-read evidence"
        status, payload = receiver.recv()
        receiver.close()
        assert status == "ok", (label, payload)
        reported[label] = payload

    for process in processes:
        process.join(timeout=30)
        assert not process.is_alive()
        assert process.exitcode == 0

    writer_results = reported["writer"]
    assert len(writer_results) == 19
    assert all(outcome == "applied" and accepted and changed for _, outcome, accepted, changed in writer_results)

    for label in ("reader-0", "reader-1"):
        observations = reported[label]
        assert len(observations) == 80
        for observation in observations:
            fencing_counter, fencing_version, resource_counter, resource_version, value, mutation_id, auto, activation, traffic = observation
            assert fencing_counter == resource_counter
            assert fencing_version == resource_version
            assert value == f"v-{fencing_counter}"
            assert mutation_id == f"m-{fencing_counter}"
            assert auto is False
            assert activation is False
            assert traffic is False

    final_pair = SQLiteTransactionConsistentFencingResourceReader(database).snapshot_pair("resource-a", "authority-a")
    assert final_pair is not None
    _assert_pair_matches_committed_generation(final_pair)
    assert final_pair.fencing.fencing_counter == 20
    assert final_pair.fencing.version == 20

    assert "local-host SQLite transactional-read coherence evidence only" in TRUTH_BOUNDARY
    assert "distributed snapshot isolation" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY


def test_snapshot_connection_is_query_only_and_rejects_write_side_effects(tmp_path: Path) -> None:
    database = tmp_path / "fencing.sqlite3"
    resource = SQLiteTransactionallyFencedProtectedResource(database)
    applied = resource.mutate("resource-a", "authority-a", 1, mutation_id="m-1", value="v-1")
    assert applied.outcome == "applied"

    reader = SQLiteTransactionConsistentFencingResourceReader(database)
    connection = reader._connect()
    try:
        query_only = connection.execute("PRAGMA query_only").fetchone()
        assert query_only == (1,)
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute(
                "UPDATE morpheus_protected_resource_state SET value = 'tampered' "
                "WHERE resource_id = 'resource-a' AND fencing_authority_id = 'authority-a'"
            )
    finally:
        connection.close()

    pair = reader.snapshot_pair("resource-a", "authority-a")
    assert pair is not None
    _assert_pair_matches_committed_generation(pair)
    assert pair.resource.value == "v-1"
    assert pair.resource.last_mutation_id == "m-1"
