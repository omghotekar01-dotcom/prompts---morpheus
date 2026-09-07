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
    "These tests provide local-host, spawned-process evidence for the transactionally fenced SQLite protected-resource reference path. "
    "They do not establish cross-host or distributed linearizability, consensus, leases, network-partition safety, storage-device or "
    "power-loss durability, arbitrary external-resource fencing, safe cutover, live replacement, HA/SLA behavior, production readiness, "
    "or any benchmark, performance-superiority, novelty, patentability or scientific-effect claim."
)


def _mutate_worker(
    database_path: str,
    resource_id: str,
    authority_id: str,
    counter: int,
    mutation_id: str,
    value: str,
    result_queue: Any,
) -> None:
    try:
        resource = SQLiteTransactionallyFencedProtectedResource(database_path)
        result = resource.mutate(
            resource_id,
            authority_id,
            counter,
            mutation_id=mutation_id,
            value=value,
        )
        snapshot = resource.snapshot(resource_id, authority_id)
        result_queue.put(
            {
                "ok": True,
                "outcome": result.outcome,
                "accepted": result.accepted,
                "state_changed": result.state_changed,
                "automatic_control_allowed": result.automatic_control_allowed,
                "activation_allowed": result.activation_allowed,
                "traffic_switching_allowed": result.traffic_switching_allowed,
                "snapshot": None
                if snapshot is None
                else (
                    snapshot.value,
                    snapshot.last_mutation_id,
                    snapshot.last_fencing_counter,
                    snapshot.resource_version,
                ),
            }
        )
    except Exception as exc:  # pragma: no cover - asserted through child result
        result_queue.put({"ok": False, "error_type": type(exc).__name__, "error": str(exc)})


def _run_process(ctx: mp.context.BaseContext, args: tuple[Any, ...]) -> dict[str, Any]:
    result_queue = ctx.Queue()
    process = ctx.Process(target=_mutate_worker, args=(*args, result_queue))
    process.start()
    process.join(timeout=20)
    assert process.exitcode == 0
    return result_queue.get(timeout=5)


def test_spawned_process_reconstruction_preserves_retry_and_stale_semantics(tmp_path: Path) -> None:
    ctx = mp.get_context("spawn")
    database = str(tmp_path / "fencing.sqlite3")

    first = _run_process(ctx, (database, "resource-a", "authority-a", 3, "m-1", "alpha"))
    equal = _run_process(ctx, (database, "resource-a", "authority-a", 3, "m-1", "alpha"))
    newer = _run_process(ctx, (database, "resource-a", "authority-a", 5, "m-2", "beta"))
    stale = _run_process(ctx, (database, "resource-a", "authority-a", 4, "m-3", "gamma"))

    assert first["ok"] is True and first["outcome"] == "applied"
    assert equal["ok"] is True and equal["outcome"] == "idempotent"
    assert equal["accepted"] is True and equal["state_changed"] is False
    assert newer["ok"] is True and newer["outcome"] == "applied"
    assert stale["ok"] is True and stale["outcome"] == "stale"
    assert stale["accepted"] is False and stale["state_changed"] is False

    reconstructed = SQLiteTransactionallyFencedProtectedResource(database)
    resource_snapshot = reconstructed.snapshot("resource-a", "authority-a")
    fencing_snapshot = SQLiteAtomicConditionalFencingBackend(database).snapshot("resource-a", "authority-a")
    assert resource_snapshot is not None and fencing_snapshot is not None
    assert (
        resource_snapshot.value,
        resource_snapshot.last_mutation_id,
        resource_snapshot.last_fencing_counter,
        resource_snapshot.resource_version,
    ) == ("beta", "m-2", 5, 2)
    assert (fencing_snapshot.fencing_counter, fencing_snapshot.version) == (5, 2)


def test_spawned_processes_competing_at_same_generation_commit_only_one_mutation(tmp_path: Path) -> None:
    ctx = mp.get_context("spawn")
    database = str(tmp_path / "fencing.sqlite3")
    seed = SQLiteTransactionallyFencedProtectedResource(database)
    assert seed.mutate("resource-a", "authority-a", 1, mutation_id="seed", value="seed").outcome == "applied"

    result_queue = ctx.Queue()
    processes = [
        ctx.Process(
            target=_mutate_worker,
            args=(database, "resource-a", "authority-a", 2, "m-a", "alpha", result_queue),
        ),
        ctx.Process(
            target=_mutate_worker,
            args=(database, "resource-a", "authority-a", 2, "m-b", "beta", result_queue),
        ),
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=20)
        assert process.exitcode == 0

    results = [result_queue.get(timeout=5), result_queue.get(timeout=5)]
    assert all(result["ok"] is True for result in results)
    outcomes = [result["outcome"] for result in results]
    assert outcomes.count("applied") == 1
    assert outcomes.count("generation_reuse_rejected") == 1

    winner = next(result for result in results if result["outcome"] == "applied")
    resource_snapshot = seed.snapshot("resource-a", "authority-a")
    fencing_snapshot = SQLiteAtomicConditionalFencingBackend(database).snapshot("resource-a", "authority-a")
    assert resource_snapshot is not None and fencing_snapshot is not None
    assert resource_snapshot.last_fencing_counter == 2
    assert resource_snapshot.resource_version == 2
    assert (resource_snapshot.value, resource_snapshot.last_mutation_id) == (winner["snapshot"][0], winner["snapshot"][1])
    assert (fencing_snapshot.fencing_counter, fencing_snapshot.version) == (2, 2)


def test_spawned_process_transactional_failure_leaves_fencing_and_resource_in_agreement(tmp_path: Path) -> None:
    ctx = mp.get_context("spawn")
    database_path = tmp_path / "fencing.sqlite3"
    database = str(database_path)
    resource = SQLiteTransactionallyFencedProtectedResource(database)
    fencing = SQLiteAtomicConditionalFencingBackend(database)
    assert resource.mutate("resource-a", "authority-a", 1, mutation_id="m-1", value="alpha").outcome == "applied"

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TRIGGER fail_spawned_resource_update BEFORE UPDATE ON morpheus_protected_resource_state "
            "BEGIN SELECT RAISE(ABORT, 'spawned injected resource mutation failure'); END"
        )

    failed = _run_process(ctx, (database, "resource-a", "authority-a", 2, "m-2", "beta"))
    assert failed["ok"] is False
    assert failed["error_type"] == "ValueError"
    assert "transactionally fenced protected-resource mutation failed" in failed["error"]

    resource_snapshot = resource.snapshot("resource-a", "authority-a")
    fencing_snapshot = fencing.snapshot("resource-a", "authority-a")
    assert resource_snapshot is not None and fencing_snapshot is not None
    assert (
        resource_snapshot.value,
        resource_snapshot.last_mutation_id,
        resource_snapshot.last_fencing_counter,
        resource_snapshot.resource_version,
    ) == ("alpha", "m-1", 1, 1)
    assert (fencing_snapshot.fencing_counter, fencing_snapshot.version) == (1, 1)

    with sqlite3.connect(database_path) as connection:
        connection.execute("DROP TRIGGER fail_spawned_resource_update")

    recovered = _run_process(ctx, (database, "resource-a", "authority-a", 2, "m-2", "beta"))
    assert recovered["ok"] is True and recovered["outcome"] == "applied"
    assert recovered["snapshot"] == ("beta", "m-2", 2, 2)


def test_spawned_process_results_never_gain_production_authority(tmp_path: Path) -> None:
    ctx = mp.get_context("spawn")
    database = str(tmp_path / "fencing.sqlite3")
    result = _run_process(ctx, (database, "resource-a", "authority-a", 1, "m-1", "alpha"))

    assert result["ok"] is True
    assert result["automatic_control_allowed"] is False
    assert result["activation_allowed"] is False
    assert result["traffic_switching_allowed"] is False
    assert "local-host, spawned-process evidence" in TRUTH_BOUNDARY
    assert "do not establish cross-host or distributed linearizability" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
