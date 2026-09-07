from __future__ import annotations

import multiprocessing as mp
from pathlib import Path
from typing import Any

from app.process_transfer_protected_resource_fencing_sqlite import SQLiteAtomicConditionalFencingBackend
from app.process_transfer_protected_resource_fencing_sqlite_resource import (
    SQLiteTransactionallyFencedProtectedResource,
)


TRUTH_BOUNDARY = (
    "These tests provide local-host SQLite concurrent replay/successor evidence only. "
    "They do not establish distributed consensus, global exactly-once semantics, lock-free progress, "
    "external-resource fencing, network-partition safety, production failover, HA/SLA behavior, or production readiness."
)


def _concurrent_mutation_worker(
    database_path: str,
    *,
    fencing_counter: int,
    mutation_id: str,
    value: str,
    start_event: Any,
    result_pipe: Any,
) -> None:
    resource = SQLiteTransactionallyFencedProtectedResource(database_path)
    if not start_event.wait(timeout=15):
        result_pipe.send(("worker_error", False, False, -1, -1, False, False, False))
        result_pipe.close()
        return

    try:
        result = resource.mutate(
            "resource-a",
            "authority-a",
            fencing_counter,
            mutation_id=mutation_id,
            value=value,
        )
        result_pipe.send(
            (
                result.outcome,
                result.accepted,
                result.state_changed,
                result.fencing_version,
                result.resource_version,
                result.automatic_control_allowed,
                result.activation_allowed,
                result.traffic_switching_allowed,
            )
        )
    except Exception as exc:  # pragma: no cover - retained as evidence diagnostics across spawned processes.
        result_pipe.send((f"worker_error:{type(exc).__name__}", False, False, -1, -1, False, False, False))
    finally:
        result_pipe.close()


def _assert_fencing_resource_agreement(
    database_path: str,
    *,
    expected_counter: int,
    expected_version: int,
    expected_value: str,
    expected_mutation_id: str,
) -> None:
    fencing = SQLiteAtomicConditionalFencingBackend(database_path).snapshot("resource-a", "authority-a")
    resource = SQLiteTransactionallyFencedProtectedResource(database_path).snapshot("resource-a", "authority-a")
    assert fencing is not None and resource is not None
    assert fencing.fencing_counter == expected_counter
    assert fencing.version == expected_version
    assert resource.last_fencing_counter == expected_counter
    assert resource.resource_version == expected_version
    assert resource.value == expected_value
    assert resource.last_mutation_id == expected_mutation_id


def test_concurrent_lost_ack_retries_conflict_and_successor_preserve_single_state_advance(tmp_path: Path) -> None:
    ctx = mp.get_context("spawn")
    database = str(tmp_path / "fencing.sqlite3")
    resource = SQLiteTransactionallyFencedProtectedResource(database)

    committed = resource.mutate(
        "resource-a",
        "authority-a",
        5,
        mutation_id="m-5",
        value="alpha",
    )
    assert committed.outcome == "applied"
    assert committed.state_changed is True
    _assert_fencing_resource_agreement(
        database,
        expected_counter=5,
        expected_version=1,
        expected_value="alpha",
        expected_mutation_id="m-5",
    )

    start_event = ctx.Event()
    attempts = [
        ("retry-1", 5, "m-5", "alpha"),
        ("retry-2", 5, "m-5", "alpha"),
        ("retry-3", 5, "m-5", "alpha"),
        ("conflict", 5, "m-5-conflict", "alpha"),
        ("successor", 6, "m-6", "beta"),
    ]

    processes: list[mp.Process] = []
    receivers: dict[str, Any] = {}
    for label, counter, mutation_id, value in attempts:
        parent_result, child_result = ctx.Pipe(duplex=False)
        process = ctx.Process(
            target=_concurrent_mutation_worker,
            kwargs={
                "database_path": database,
                "fencing_counter": counter,
                "mutation_id": mutation_id,
                "value": value,
                "start_event": start_event,
                "result_pipe": child_result,
            },
        )
        process.start()
        child_result.close()
        processes.append(process)
        receivers[label] = parent_result

    start_event.set()

    results: dict[str, tuple[Any, ...]] = {}
    for label, receiver in receivers.items():
        assert receiver.poll(20), f"{label} did not report a concurrent mutation result"
        results[label] = receiver.recv()
        receiver.close()

    for process in processes:
        process.join(timeout=20)
        assert not process.is_alive()
        assert process.exitcode == 0

    for label, result in results.items():
        assert not str(result[0]).startswith("worker_error"), (label, result)
        assert result[5:] == (False, False, False)

    retry_results = [results["retry-1"], results["retry-2"], results["retry-3"]]
    # If a retry reaches SQLite before the successor it is an exact idempotent replay;
    # if it reaches SQLite after the successor it is stale. Neither path may mutate state.
    assert {result[0] for result in retry_results} <= {"idempotent", "stale"}
    assert all(result[2] is False for result in retry_results)

    conflicting_reuse = results["conflict"]
    # The same-generation conflicting identity is rejected while generation 5 is current,
    # or is stale if the valid successor has already committed. It can never apply.
    assert conflicting_reuse[0] in {"generation_reuse_rejected", "stale"}
    assert conflicting_reuse[1] is False
    assert conflicting_reuse[2] is False

    successor = results["successor"]
    assert successor[0] == "applied"
    assert successor[1] is True
    assert successor[2] is True
    assert successor[3] == 2
    assert successor[4] == 2

    # Across all five concurrent attempts, the already-committed retry generation cannot
    # produce another state transition; only the valid strictly newer generation advances.
    assert sum(1 for result in results.values() if result[2] is True) == 1

    _assert_fencing_resource_agreement(
        database,
        expected_counter=6,
        expected_version=2,
        expected_value="beta",
        expected_mutation_id="m-6",
    )

    reconstructed = SQLiteTransactionallyFencedProtectedResource(database)
    exact_successor_retry = reconstructed.mutate(
        "resource-a",
        "authority-a",
        6,
        mutation_id="m-6",
        value="beta",
    )
    assert exact_successor_retry.outcome == "idempotent"
    assert exact_successor_retry.accepted is True
    assert exact_successor_retry.state_changed is False
    assert exact_successor_retry.fencing_version == 2
    assert exact_successor_retry.resource_version == 2

    _assert_fencing_resource_agreement(
        database,
        expected_counter=6,
        expected_version=2,
        expected_value="beta",
        expected_mutation_id="m-6",
    )
    assert "local-host SQLite concurrent replay/successor evidence only" in TRUTH_BOUNDARY
    assert "global exactly-once semantics" in TRUTH_BOUNDARY
    assert "lock-free progress" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
