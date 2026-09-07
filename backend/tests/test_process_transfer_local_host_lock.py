from __future__ import annotations

import multiprocessing
import os
from pathlib import Path

from app.process_transfer_local_host_lock import LocalHostFileLock, TRUTH_BOUNDARY as LOCK_TRUTH_BOUNDARY
from app.process_transfer_protected_resource_fencing_durable import DurableProtectedResourceFencingModel


def _hold_lock(lock_path: str, ready, release) -> None:
    lock = LocalHostFileLock(lock_path)
    with lock:
        ready.set()
        if not release.wait(timeout=20):
            raise RuntimeError("timed out waiting to release held local-host lock")


def _acquire_and_signal(lock_path: str, acquired) -> None:
    with LocalHostFileLock(lock_path):
        acquired.set()


def _crash_while_holding(lock_path: str, ready) -> None:
    lock = LocalHostFileLock(lock_path)
    lock.acquire()
    ready.set()
    os._exit(23)


def _validate_token(state_path: str, counter: int, started, done, result_queue) -> None:
    started.set()
    model = DurableProtectedResourceFencingModel(state_path, "resource-a", "fence-a")
    decision = model.validate_fencing_token("resource-a", "fence-a", counter)
    result_queue.put((decision.fencing_counter, decision.accepted))
    done.set()


def _spawn_context():
    return multiprocessing.get_context("spawn")


def test_local_host_lock_blocks_second_process_until_release(tmp_path: Path) -> None:
    ctx = _spawn_context()
    lock_path = str(tmp_path / ".state.morpheus.lock")
    ready = ctx.Event()
    release = ctx.Event()
    acquired = ctx.Event()

    holder = ctx.Process(target=_hold_lock, args=(lock_path, ready, release))
    holder.start()
    assert ready.wait(timeout=10)

    contender = ctx.Process(target=_acquire_and_signal, args=(lock_path, acquired))
    contender.start()
    assert acquired.wait(timeout=0.25) is False

    release.set()
    assert acquired.wait(timeout=10)
    holder.join(timeout=10)
    contender.join(timeout=10)
    assert holder.exitcode == 0
    assert contender.exitcode == 0


def test_local_host_lock_is_released_after_process_abandonment(tmp_path: Path) -> None:
    ctx = _spawn_context()
    lock_path = str(tmp_path / ".state.morpheus.lock")
    ready = ctx.Event()

    crashing = ctx.Process(target=_crash_while_holding, args=(lock_path, ready))
    crashing.start()
    assert ready.wait(timeout=10)
    crashing.join(timeout=10)
    assert crashing.exitcode == 23

    acquired = ctx.Event()
    successor = ctx.Process(target=_acquire_and_signal, args=(lock_path, acquired))
    successor.start()
    assert acquired.wait(timeout=10)
    successor.join(timeout=10)
    assert successor.exitcode == 0


def test_durable_fencing_transition_is_serialized_across_processes(tmp_path: Path) -> None:
    state_path = tmp_path / "fencing-state.json"
    seed = DurableProtectedResourceFencingModel(state_path, "resource-a", "fence-a")
    assert seed.validate_fencing_token("resource-a", "fence-a", 10).accepted is True

    ctx = _spawn_context()
    ready = ctx.Event()
    release = ctx.Event()
    started = ctx.Event()
    done = ctx.Event()
    result_queue = ctx.Queue()

    holder = ctx.Process(target=_hold_lock, args=(str(seed._host_lock_path), ready, release))
    holder.start()
    assert ready.wait(timeout=10)

    contender = ctx.Process(target=_validate_token, args=(str(state_path), 11, started, done, result_queue))
    contender.start()
    assert started.wait(timeout=10)
    assert done.wait(timeout=0.25) is False

    release.set()
    assert done.wait(timeout=10)
    assert result_queue.get(timeout=5) == (11, True)

    holder.join(timeout=10)
    contender.join(timeout=10)
    assert holder.exitcode == 0
    assert contender.exitcode == 0
    assert DurableProtectedResourceFencingModel(state_path, "resource-a", "fence-a").snapshot().highest_accepted_fencing_counter == 11


def test_newer_cross_process_generation_preserves_stale_and_equal_semantics(tmp_path: Path) -> None:
    state_path = tmp_path / "fencing-state.json"
    initial = DurableProtectedResourceFencingModel(state_path, "resource-a", "fence-a")
    assert initial.validate_fencing_token("resource-a", "fence-a", 20).accepted is True

    ctx = _spawn_context()
    started = ctx.Event()
    done = ctx.Event()
    result_queue = ctx.Queue()
    worker = ctx.Process(target=_validate_token, args=(str(state_path), 22, started, done, result_queue))
    worker.start()
    assert started.wait(timeout=10)
    assert done.wait(timeout=10)
    assert result_queue.get(timeout=5) == (22, True)
    worker.join(timeout=10)
    assert worker.exitcode == 0

    restarted = DurableProtectedResourceFencingModel(state_path, "resource-a", "fence-a")
    assert restarted.validate_fencing_token("resource-a", "fence-a", 21).accepted is False
    assert restarted.validate_fencing_token("resource-a", "fence-a", 22).accepted is True
    assert restarted.validate_fencing_token("resource-a", "fence-a", 23).accepted is True


def test_lock_truth_boundary_is_explicitly_local_and_advisory() -> None:
    lowered = LOCK_TRUTH_BOUNDARY.lower()
    assert "local-host advisory" in lowered
    assert "cooperating morpheus processes" in lowered
    assert "non-cooperating process" in lowered
    assert "does not provide distributed mutual exclusion" in lowered
    assert "power-loss durability" in lowered
    assert "linearizability proof" in lowered
