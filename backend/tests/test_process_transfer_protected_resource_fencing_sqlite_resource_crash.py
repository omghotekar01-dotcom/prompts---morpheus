from __future__ import annotations

import multiprocessing as mp
from pathlib import Path
import sqlite3
from typing import Any

from app.process_transfer_protected_resource_fencing_sqlite import SQLiteAtomicConditionalFencingBackend
from app.process_transfer_protected_resource_fencing_sqlite_resource import (
    SQLiteTransactionallyFencedProtectedResource,
)


TRUTH_BOUNDARY = (
    "These tests provide local-host SQLite process-termination recovery evidence only. "
    "They do not establish power-loss durability, storage-device correctness, distributed failure recovery, "
    "external protected-resource fencing, activation authority, traffic-switching authority, HA/SLA behavior, "
    "or production readiness."
)


def _hold_uncommitted_transition(
    database_path: str,
    *,
    first_mutation: bool,
    ready: Any,
    release: Any,
) -> None:
    connection = sqlite3.connect(database_path, timeout=5.0, isolation_level=None)
    try:
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("BEGIN IMMEDIATE")
        if first_mutation:
            connection.execute(
                "INSERT INTO morpheus_fencing_state(resource_id, fencing_authority_id, fencing_counter, version) "
                "VALUES (?, ?, ?, ?)",
                ("resource-a", "authority-a", 1, 1),
            )
            connection.execute(
                "INSERT INTO morpheus_protected_resource_state(resource_id, fencing_authority_id, resource_version, value, "
                "last_mutation_id, last_fencing_counter) VALUES (?, ?, ?, ?, ?, ?)",
                ("resource-a", "authority-a", 1, "alpha", "m-1", 1),
            )
        else:
            connection.execute(
                "UPDATE morpheus_fencing_state SET fencing_counter = ?, version = ? "
                "WHERE resource_id = ? AND fencing_authority_id = ? AND version = ?",
                (2, 2, "resource-a", "authority-a", 1),
            )
            connection.execute(
                "UPDATE morpheus_protected_resource_state SET resource_version = ?, value = ?, last_mutation_id = ?, "
                "last_fencing_counter = ? WHERE resource_id = ? AND fencing_authority_id = ? AND resource_version = ?",
                (2, "beta", "m-2", 2, "resource-a", "authority-a", 1),
            )
        ready.send("uncommitted")
        release.wait(30)
    finally:
        connection.close()


def _start_uncommitted_worker(
    ctx: mp.context.BaseContext,
    database: str,
    *,
    first_mutation: bool,
) -> mp.Process:
    parent_ready, child_ready = ctx.Pipe(duplex=False)
    release = ctx.Event()
    process = ctx.Process(
        target=_hold_uncommitted_transition,
        kwargs={
            "database_path": database,
            "first_mutation": first_mutation,
            "ready": child_ready,
            "release": release,
        },
    )
    process.start()
    child_ready.close()
    assert parent_ready.poll(10), "child did not reach the uncommitted SQLite transaction boundary"
    assert parent_ready.recv() == "uncommitted"
    parent_ready.close()
    return process


def test_terminated_process_rolls_back_uncommitted_advance_and_releases_write_lock(tmp_path: Path) -> None:
    ctx = mp.get_context("spawn")
    database = str(tmp_path / "fencing.sqlite3")
    resource = SQLiteTransactionallyFencedProtectedResource(database)
    fencing = SQLiteAtomicConditionalFencingBackend(database)
    assert resource.mutate("resource-a", "authority-a", 1, mutation_id="m-1", value="alpha").outcome == "applied"

    process = _start_uncommitted_worker(ctx, database, first_mutation=False)
    process.terminate()
    process.join(timeout=10)
    assert not process.is_alive()
    assert process.exitcode is not None and process.exitcode != 0

    reconstructed = SQLiteTransactionallyFencedProtectedResource(database)
    resource_snapshot = reconstructed.snapshot("resource-a", "authority-a")
    fencing_snapshot = SQLiteAtomicConditionalFencingBackend(database).snapshot("resource-a", "authority-a")
    assert resource_snapshot is not None and fencing_snapshot is not None
    assert (
        resource_snapshot.value,
        resource_snapshot.last_mutation_id,
        resource_snapshot.last_fencing_counter,
        resource_snapshot.resource_version,
    ) == ("alpha", "m-1", 1, 1)
    assert (fencing_snapshot.fencing_counter, fencing_snapshot.version) == (1, 1)

    recovered = reconstructed.mutate("resource-a", "authority-a", 2, mutation_id="m-2", value="beta")
    assert recovered.outcome == "applied"
    assert recovered.accepted is True and recovered.state_changed is True
    assert recovered.automatic_control_allowed is False
    assert recovered.activation_allowed is False
    assert recovered.traffic_switching_allowed is False


def test_terminated_first_mutation_leaves_no_partial_state_and_allows_clean_retry(tmp_path: Path) -> None:
    ctx = mp.get_context("spawn")
    database = str(tmp_path / "fencing.sqlite3")
    resource = SQLiteTransactionallyFencedProtectedResource(database)

    process = _start_uncommitted_worker(ctx, database, first_mutation=True)
    process.terminate()
    process.join(timeout=10)
    assert not process.is_alive()
    assert process.exitcode is not None and process.exitcode != 0

    reconstructed = SQLiteTransactionallyFencedProtectedResource(database)
    fencing = SQLiteAtomicConditionalFencingBackend(database)
    assert reconstructed.snapshot("resource-a", "authority-a") is None
    assert fencing.snapshot("resource-a", "authority-a") is None

    recovered = reconstructed.mutate("resource-a", "authority-a", 1, mutation_id="m-1", value="alpha")
    assert recovered.outcome == "applied"
    assert recovered.accepted is True and recovered.state_changed is True
    assert recovered.fencing_version == 1
    assert recovered.resource_version == 1
    assert recovered.automatic_control_allowed is False
    assert recovered.activation_allowed is False
    assert recovered.traffic_switching_allowed is False
    assert "local-host SQLite process-termination recovery evidence only" in TRUTH_BOUNDARY
    assert "power-loss durability" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
