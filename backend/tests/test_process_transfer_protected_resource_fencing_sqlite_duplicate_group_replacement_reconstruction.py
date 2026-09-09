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
from test_process_transfer_protected_resource_fencing_sqlite_partial_duplicate_group_waiter_loss import (
    _terminate_waiter,
)
from test_process_transfer_protected_resource_fencing_sqlite_replacement_waiter_reconstruction_recovery import (
    _start_replacement_waiter,
)


BASE_COUNTER = 3701


def test_duplicate_group_replacements_reconstructed_before_rollback_converge_once(
    tmp_path: Path,
) -> None:
    database = tmp_path / "duplicate-group-replacement-reconstruction.sqlite3"
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
        name="duplicate-group-replacement-holder",
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

    original_specs = {
        "a_lost": (mutation_a_id, mutation_a_value),
        "a_survivor": (mutation_a_id, mutation_a_value),
        "b_lost": (mutation_b_id, mutation_b_value),
        "b_survivor": (mutation_b_id, mutation_b_value),
    }
    original_waiters: dict[str, mp.Process] = {}
    original_results = {}
    for label, (mutation_id, value) in original_specs.items():
        process, results = _start_replacement_waiter(
            context,
            database,
            pending_counter=pending_counter,
            pending_mutation_id=mutation_id,
            pending_value=value,
            label=f"duplicate-group-original-{label}",
        )
        original_waiters[label] = process
        original_results[label] = results

    assert all(process.is_alive() for process in original_waiters.values())
    assert holder.is_alive()
    _assert_committed_pair(database, long_lived_reader, current_expected)
    _assert_committed_pair(database, fresh_reader, current_expected)

    _terminate_waiter(original_waiters["a_lost"], "lost original waiter from mutation A")
    _terminate_waiter(original_waiters["b_lost"], "lost original waiter from mutation B")

    assert holder.is_alive()
    assert original_waiters["a_survivor"].is_alive()
    assert original_waiters["b_survivor"].is_alive()
    _assert_committed_pair(database, long_lived_reader, current_expected)
    _assert_committed_pair(database, fresh_reader, current_expected)

    # E81 evidence gate: replace both deliberately lost duplicate-group members while
    # the staged holder still owns SQLite's write path. These replacement processes are
    # newly reconstructed adapters, not continuations of the terminated writer state.
    replacement_specs = {
        "a_replacement": (mutation_a_id, mutation_a_value),
        "b_replacement": (mutation_b_id, mutation_b_value),
    }
    replacement_waiters: dict[str, mp.Process] = {}
    replacement_results = {}
    for label, (mutation_id, value) in replacement_specs.items():
        process, results = _start_replacement_waiter(
            context,
            database,
            pending_counter=pending_counter,
            pending_mutation_id=mutation_id,
            pending_value=value,
            label=f"duplicate-group-{label}",
        )
        replacement_waiters[label] = process
        replacement_results[label] = results

    live_waiters = {
        "a_survivor": original_waiters["a_survivor"],
        "a_replacement": replacement_waiters["a_replacement"],
        "b_survivor": original_waiters["b_survivor"],
        "b_replacement": replacement_waiters["b_replacement"],
    }
    live_results = {
        "a_survivor": original_results["a_survivor"],
        "a_replacement": replacement_results["a_replacement"],
        "b_survivor": original_results["b_survivor"],
        "b_replacement": replacement_results["b_replacement"],
    }

    assert all(process.is_alive() for process in live_waiters.values())
    assert holder.is_alive()
    _assert_committed_pair(database, long_lived_reader, current_expected)
    _assert_committed_pair(database, fresh_reader, current_expected)

    _terminate_holder(holder)

    outcomes = {label: live_results[label].get(timeout=10.0) for label in live_waiters}
    for label, process in live_waiters.items():
        _join_cleanly(process, f"duplicate-group live waiter {label}")

    assert all(outcome["kind"] == "outcome" for outcome in outcomes.values())
    result_names = [outcome["outcome"] for outcome in outcomes.values()]
    assert result_names.count("applied") == 1
    assert result_names.count("idempotent") == 1
    assert result_names.count("generation_reuse_rejected") == 2

    a_names = [
        outcomes["a_survivor"]["outcome"],
        outcomes["a_replacement"]["outcome"],
    ]
    b_names = [
        outcomes["b_survivor"]["outcome"],
        outcomes["b_replacement"]["outcome"],
    ]
    winning_group = "a" if "applied" in a_names else "b"
    winning_names = a_names if winning_group == "a" else b_names
    losing_names = b_names if winning_group == "a" else a_names
    assert sorted(winning_names) == ["applied", "idempotent"]
    assert losing_names == ["generation_reuse_rejected", "generation_reuse_rejected"]

    if winning_group == "a":
        winning_mutation_id = mutation_a_id
        winning_value = mutation_a_value
        losing_mutation_id = mutation_b_id
        losing_value = mutation_b_value
    else:
        winning_mutation_id = mutation_b_id
        winning_value = mutation_b_value
        losing_mutation_id = mutation_a_id
        losing_value = mutation_a_value

    for label, outcome in outcomes.items():
        assert outcome["fencing_version"] == pending_version, label
        assert outcome["resource_version"] == pending_version, label
        assert outcome["automatic_control_allowed"] is False, label
        assert outcome["activation_allowed"] is False, label
        assert outcome["traffic_switching_allowed"] is False, label
        if outcome["outcome"] == "applied":
            assert outcome["accepted"] is True, label
            assert outcome["state_changed"] is True, label
        elif outcome["outcome"] == "idempotent":
            assert outcome["accepted"] is True, label
            assert outcome["state_changed"] is False, label
        else:
            assert outcome["outcome"] == "generation_reuse_rejected", label
            assert outcome["accepted"] is False, label
            assert outcome["state_changed"] is False, label

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


def test_duplicate_group_replacement_reconstruction_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "power-loss" in combined
    assert "production readiness" in combined
    assert "performance" in combined
    assert "novelty" in combined
