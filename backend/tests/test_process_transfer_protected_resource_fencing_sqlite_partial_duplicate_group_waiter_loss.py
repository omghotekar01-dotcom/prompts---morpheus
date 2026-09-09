from __future__ import annotations

import multiprocessing as mp
from pathlib import Path

from app.process_transfer_protected_resource_fencing_sqlite_resource import (
    SQLiteTransactionallyFencedProtectedResource,
    TRUTH_BOUNDARY as RESOURCE_TRUTH_BOUNDARY,
)
from app.process_transfer_protected_resource_fencing_sqlite_snapshot import (
    SQLiteTransactionConsistentFencingResourceReader,
    TRUTH_BOUNDARY as READER_TRUTH_BOUNDARY,
)
from test_process_transfer_protected_resource_fencing_sqlite_busy_timeout_recovery import (
    _terminate_holder,
)
from test_process_transfer_protected_resource_fencing_sqlite_long_waiter_loss_reconstruction import (
    _assert_committed_pair,
)
from test_process_transfer_protected_resource_fencing_sqlite_mixed_contention_forced_loss import (
    AUTHORITY_ID,
    RESOURCE_ID,
    _assert_write_lock_released,
    _expected_pair,
    _stage_uncommitted_next_generation,
)
from test_process_transfer_protected_resource_fencing_sqlite_mixed_timeout_waiter_recovery import (
    _join_cleanly,
)
from test_process_transfer_protected_resource_fencing_sqlite_replacement_waiter_reconstruction_recovery import (
    _start_replacement_waiter,
)


BASE_COUNTER = 3601


def _terminate_waiter(process: mp.Process, label: str) -> None:
    assert process.is_alive(), label
    process.terminate()
    process.join(timeout=10.0)
    assert not process.is_alive(), label
    assert process.exitcode is not None, label
    assert process.exitcode != 0, label


def test_partial_duplicate_group_waiter_loss_preserves_single_generation_recovery(
    tmp_path: Path,
) -> None:
    database = tmp_path / "partial-duplicate-group-waiter-loss.sqlite3"
    writer = SQLiteTransactionallyFencedProtectedResource(database, timeout_seconds=3.0)
    long_lived_reader = SQLiteTransactionConsistentFencingResourceReader(
        database, timeout_seconds=3.0
    )
    context = mp.get_context("spawn")

    current_counter = BASE_COUNTER
    current_version = 1
    current_mutation_id = f"mutation-{current_counter}"
    current_value = f"committed-{current_counter}"
    initial = writer.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        current_counter,
        mutation_id=current_mutation_id,
        value=current_value,
    )
    assert initial.outcome == "applied"
    assert initial.accepted is True
    assert initial.state_changed is True
    assert initial.fencing_version == current_version
    assert initial.resource_version == current_version
    assert initial.automatic_control_allowed is False
    assert initial.activation_allowed is False
    assert initial.traffic_switching_allowed is False

    current_expected = _expected_pair(
        counter=current_counter,
        version=current_version,
        mutation_id=current_mutation_id,
        value=current_value,
    )
    _assert_committed_pair(database, long_lived_reader, current_expected)

    pending_counter = current_counter + 1
    pending_version = current_version + 1
    mutation_a_id = f"mutation-{pending_counter}-a"
    mutation_a_value = f"committed-{pending_counter}-a"
    mutation_b_id = f"mutation-{pending_counter}-b"
    mutation_b_value = f"committed-{pending_counter}-b"

    ready = context.Queue()
    hold = context.Event()
    holder = context.Process(
        target=_stage_uncommitted_next_generation,
        args=(
            str(database),
            ready,
            hold,
            pending_counter,
            pending_version,
        ),
        name="partial-duplicate-group-holder",
    )
    holder.start()
    assert ready.get(timeout=10.0) == {
        "counter": pending_counter,
        "version": pending_version,
    }
    assert holder.is_alive()

    fresh_reader = SQLiteTransactionConsistentFencingResourceReader(
        database, timeout_seconds=3.0
    )
    _assert_committed_pair(database, long_lived_reader, current_expected)
    _assert_committed_pair(database, fresh_reader, current_expected)

    waiter_specs = {
        "a_lost": (mutation_a_id, mutation_a_value),
        "a_survivor": (mutation_a_id, mutation_a_value),
        "b_lost": (mutation_b_id, mutation_b_value),
        "b_survivor": (mutation_b_id, mutation_b_value),
    }
    waiters: dict[str, mp.Process] = {}
    result_queues = {}
    for label, (mutation_id, value) in waiter_specs.items():
        process, results = _start_replacement_waiter(
            context,
            database,
            pending_counter=pending_counter,
            pending_mutation_id=mutation_id,
            pending_value=value,
            label=f"partial-group-{label}",
        )
        waiters[label] = process
        result_queues[label] = results

    # E80 evidence gate: process loss is introduced inside both duplicate groups while
    # the staged transaction still owns SQLite's write path. All waiters begin from
    # independently reconstructed production adapters and the pending generation stays
    # invisible to both long-lived and freshly reconstructed readers.
    assert all(process.is_alive() for process in waiters.values())
    assert holder.is_alive()
    _assert_committed_pair(database, long_lived_reader, current_expected)
    _assert_committed_pair(database, fresh_reader, current_expected)

    _terminate_waiter(waiters["a_lost"], "lost waiter from mutation A")
    _terminate_waiter(waiters["b_lost"], "lost waiter from mutation B")

    # Losing blocked processes must not consume or expose the staged generation, and
    # their termination must not disturb either the live holder or the surviving writers.
    assert holder.is_alive()
    assert waiters["a_survivor"].is_alive()
    assert waiters["b_survivor"].is_alive()
    _assert_committed_pair(database, long_lived_reader, current_expected)
    _assert_committed_pair(database, fresh_reader, current_expected)

    _terminate_holder(holder)

    survivor_names = ("a_survivor", "b_survivor")
    outcomes = {
        label: result_queues[label].get(timeout=10.0) for label in survivor_names
    }
    for label in survivor_names:
        _join_cleanly(waiters[label], f"partial duplicate-group survivor {label}")

    assert all(outcome["kind"] == "outcome" for outcome in outcomes.values())
    survivor_outcomes = [outcome["outcome"] for outcome in outcomes.values()]
    assert survivor_outcomes.count("applied") == 1
    assert survivor_outcomes.count("generation_reuse_rejected") == 1

    winning_name = next(
        name for name, outcome in outcomes.items() if outcome["outcome"] == "applied"
    )
    if winning_name.startswith("a_"):
        winning_mutation_id = mutation_a_id
        winning_value = mutation_a_value
        losing_mutation_id = mutation_b_id
        losing_value = mutation_b_value
    else:
        winning_mutation_id = mutation_b_id
        winning_value = mutation_b_value
        losing_mutation_id = mutation_a_id
        losing_value = mutation_a_value

    for name, outcome in outcomes.items():
        assert outcome["fencing_version"] == pending_version, name
        assert outcome["resource_version"] == pending_version, name
        assert outcome["automatic_control_allowed"] is False, name
        assert outcome["activation_allowed"] is False, name
        assert outcome["traffic_switching_allowed"] is False, name
        if outcome["outcome"] == "applied":
            assert outcome["accepted"] is True, name
            assert outcome["state_changed"] is True, name
        else:
            assert outcome["outcome"] == "generation_reuse_rejected", name
            assert outcome["accepted"] is False, name
            assert outcome["state_changed"] is False, name

    recovered_expected = _expected_pair(
        counter=pending_counter,
        version=pending_version,
        mutation_id=winning_mutation_id,
        value=winning_value,
    )
    _assert_committed_pair(database, long_lived_reader, recovered_expected)
    _assert_committed_pair(database, fresh_reader, recovered_expected)
    fresh_after_recovery = SQLiteTransactionConsistentFencingResourceReader(
        database, timeout_seconds=3.0
    )
    _assert_committed_pair(database, fresh_after_recovery, recovered_expected)
    _assert_write_lock_released(database)

    # Reconstruct both logical requests after recovery. The exact winner must converge
    # idempotently; reuse of the consumed generation by the conflict must remain rejected.
    replay_writer = SQLiteTransactionallyFencedProtectedResource(
        database, timeout_seconds=3.0
    )
    winning_replay = replay_writer.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        pending_counter,
        mutation_id=winning_mutation_id,
        value=winning_value,
    )
    assert winning_replay.outcome == "idempotent"
    assert winning_replay.accepted is True
    assert winning_replay.state_changed is False
    assert winning_replay.fencing_version == pending_version
    assert winning_replay.resource_version == pending_version
    assert winning_replay.automatic_control_allowed is False
    assert winning_replay.activation_allowed is False
    assert winning_replay.traffic_switching_allowed is False

    losing_replay = SQLiteTransactionallyFencedProtectedResource(
        database, timeout_seconds=3.0
    ).mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        pending_counter,
        mutation_id=losing_mutation_id,
        value=losing_value,
    )
    assert losing_replay.outcome == "generation_reuse_rejected"
    assert losing_replay.accepted is False
    assert losing_replay.state_changed is False
    assert losing_replay.fencing_version == pending_version
    assert losing_replay.resource_version == pending_version

    stale = replay_writer.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        current_counter,
        mutation_id=current_mutation_id,
        value=current_value,
    )
    assert stale.outcome == "stale"
    assert stale.accepted is False
    assert stale.state_changed is False
    assert stale.fencing_version == pending_version
    assert stale.resource_version == pending_version

    _assert_committed_pair(database, long_lived_reader, recovered_expected)
    _assert_write_lock_released(database)

    successor_counter = pending_counter + 1
    successor = replay_writer.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        successor_counter,
        mutation_id=f"mutation-{successor_counter}-successor",
        value=f"committed-{successor_counter}-successor",
    )
    assert successor.outcome == "applied"
    assert successor.accepted is True
    assert successor.state_changed is True
    assert successor.fencing_version == pending_version + 1
    assert successor.resource_version == pending_version + 1
    assert successor.automatic_control_allowed is False
    assert successor.activation_allowed is False
    assert successor.traffic_switching_allowed is False
    _assert_write_lock_released(database)


def test_partial_duplicate_group_waiter_loss_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "power-loss" in combined
    assert "production readiness" in combined
    assert "performance" in combined
    assert "novelty" in combined
