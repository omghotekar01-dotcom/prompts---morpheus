from __future__ import annotations

import multiprocessing
from pathlib import Path
from queue import Empty

from app.process_transfer_protected_resource_fencing_sqlite import SQLiteAtomicConditionalFencingBackend


PROCESS_EVIDENCE_BOUNDARY = (
    "These tests exercise independently spawned local-host Python processes against one SQLite database file. "
    "They do not establish distributed or cross-host linearizability, consensus, leases, protected-resource enforcement, "
    "power-loss durability, HA/SLA behavior, production readiness, or benchmark/performance claims."
)


def _conditional_write_worker(
    database_path: str,
    resource_id: str,
    fencing_authority_id: str,
    fencing_counter: int,
    expected_version: int | None,
    start_event: object,
    result_queue: object,
) -> None:
    try:
        wait = getattr(start_event, "wait")
        put = getattr(result_queue, "put")
        if not wait(15):
            put(("error", "start-timeout"))
            return
        backend = SQLiteAtomicConditionalFencingBackend(Path(database_path), timeout_seconds=10.0)
        result = backend.conditional_write(
            resource_id,
            fencing_authority_id,
            fencing_counter,
            expected_version=expected_version,
        )
        put(
            (
                "ok",
                result.outcome,
                result.observed_fencing_counter,
                result.observed_version,
                result.accepted,
                result.state_changed,
                result.automatic_control_allowed,
                result.activation_allowed,
                result.traffic_switching_allowed,
            )
        )
    except Exception as exc:  # pragma: no cover - surfaced to the parent as evidence
        getattr(result_queue, "put")(("error", type(exc).__name__, str(exc)))


def _spawn_write(
    context: multiprocessing.context.BaseContext,
    database: Path,
    counter: int,
    expected_version: int | None,
) -> tuple[object, ...]:
    start_event = context.Event()
    result_queue = context.Queue()
    process = context.Process(
        target=_conditional_write_worker,
        args=(str(database), "resource-a", "authority-a", counter, expected_version, start_event, result_queue),
    )
    process.start()
    start_event.set()
    process.join(30)
    assert not process.is_alive(), "spawned SQLite fencing worker did not terminate"
    assert process.exitcode == 0
    try:
        result = result_queue.get(timeout=5)
    except Empty as exc:  # pragma: no cover - diagnostic guard
        raise AssertionError("spawned SQLite fencing worker returned no evidence") from exc
    finally:
        result_queue.close()
        result_queue.join_thread()
    assert result[0] == "ok", result
    return result


def test_spawned_process_reconstruction_preserves_stale_equal_and_newer_semantics(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    database = tmp_path / "fencing.sqlite3"
    seed = SQLiteAtomicConditionalFencingBackend(database)
    first = seed.conditional_write("resource-a", "authority-a", 10, expected_version=None)
    assert (first.outcome, first.observed_version) == ("applied", 1)

    equal = _spawn_write(context, database, 10, 1)
    stale = _spawn_write(context, database, 9, 1)
    newer = _spawn_write(context, database, 11, 1)

    assert (equal[1], equal[4], equal[5]) == ("idempotent", True, False)
    assert (stale[1], stale[4], stale[5]) == ("stale", False, False)
    assert (newer[1], newer[2], newer[3], newer[4], newer[5]) == ("applied", 11, 2, True, True)

    reconstructed = SQLiteAtomicConditionalFencingBackend(database)
    snapshot = reconstructed.snapshot("resource-a", "authority-a")
    assert snapshot is not None
    assert (snapshot.fencing_counter, snapshot.version) == (11, 2)


def test_competing_spawned_processes_do_not_both_apply_one_predecessor(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    database = tmp_path / "fencing.sqlite3"
    seed = SQLiteAtomicConditionalFencingBackend(database)
    assert seed.conditional_write("resource-a", "authority-a", 1, expected_version=None).outcome == "applied"

    start_event = context.Event()
    result_queue = context.Queue()
    processes = [
        context.Process(
            target=_conditional_write_worker,
            args=(str(database), "resource-a", "authority-a", counter, 1, start_event, result_queue),
        )
        for counter in (2, 3)
    ]
    for process in processes:
        process.start()
    start_event.set()
    for process in processes:
        process.join(30)
        assert not process.is_alive(), "competing SQLite fencing worker did not terminate"
        assert process.exitcode == 0

    results: list[tuple[object, ...]] = []
    try:
        for _ in processes:
            results.append(result_queue.get(timeout=5))
    except Empty as exc:  # pragma: no cover - diagnostic guard
        raise AssertionError("competing SQLite fencing worker returned no evidence") from exc
    finally:
        result_queue.close()
        result_queue.join_thread()

    assert all(result[0] == "ok" for result in results), results
    outcomes = [result[1] for result in results]
    assert outcomes.count("applied") == 1
    assert set(outcomes) <= {"applied", "conflict", "stale"}

    reconstructed = SQLiteAtomicConditionalFencingBackend(database)
    snapshot = reconstructed.snapshot("resource-a", "authority-a")
    assert snapshot is not None
    assert snapshot.version == 2
    assert snapshot.fencing_counter in {2, 3}


def test_spawned_process_results_cannot_escalate_runtime_authority(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    database = tmp_path / "fencing.sqlite3"
    SQLiteAtomicConditionalFencingBackend(database)

    result = _spawn_write(context, database, 4, None)

    assert result[1] == "applied"
    assert result[6] is False
    assert result[7] is False
    assert result[8] is False
    assert "local-host Python processes" in PROCESS_EVIDENCE_BOUNDARY
    assert "do not establish distributed or cross-host linearizability" in PROCESS_EVIDENCE_BOUNDARY
    assert "production readiness" in PROCESS_EVIDENCE_BOUNDARY
