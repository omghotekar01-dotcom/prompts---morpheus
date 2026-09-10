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
from test_process_transfer_protected_resource_fencing_sqlite_duplicate_group_asymmetric_reconstruction import (
    _start_waiter,
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


BASE_COUNTER = 5101


def _run_multiplicity_generation(
    *,
    context: mp.context.BaseContext,
    database: Path,
    long_lived_reader: SQLiteTransactionConsistentFencingResourceReader,
    current_expected: dict[str, object],
    pending_counter: int,
    pending_version: int,
    triplicate_group: str,
) -> tuple[str, str, dict[str, object]]:
    duplicate_group = "b" if triplicate_group == "a" else "a"
    multiplicities = {duplicate_group: 2, triplicate_group: 3}
    mutation_ids = {
        "a": f"mutation-{pending_counter}-a",
        "b": f"mutation-{pending_counter}-b",
    }
    values = {
        "a": f"committed-{pending_counter}-a",
        "b": f"committed-{pending_counter}-b",
    }

    ready = context.Queue()
    hold = context.Event()
    holder = context.Process(
        target=_stage_uncommitted_next_generation,
        args=(str(database), ready, hold, pending_counter, pending_version),
        name=f"multiplicity-holder-{pending_counter}",
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

    waiters: dict[str, mp.Process] = {}
    result_queues = {}
    group_labels: dict[str, list[str]] = {"a": [], "b": []}

    for group in ("a", "b"):
        for index in range(1, multiplicities[group] + 1):
            label = f"{group}_{index}"
            process, results = _start_waiter(
                context,
                database,
                counter=pending_counter,
                mutation_id=mutation_ids[group],
                value=values[group],
                label=f"multiplicity-{pending_counter}-{group}-{index}",
            )
            waiters[label] = process
            result_queues[label] = results
            group_labels[group].append(label)

    assert all(process.is_alive() for process in waiters.values())
    assert holder.is_alive()
    _assert_committed_pair(database, long_lived_reader, current_expected)
    _assert_committed_pair(database, fresh_reader, current_expected)

    _terminate_holder(holder)

    outcomes = {
        label: result_queues[label].get(timeout=10.0) for label in waiters
    }
    for label, process in waiters.items():
        _join_cleanly(process, f"group-multiplicity waiter {label}")

    assert all(outcome["kind"] == "outcome" for outcome in outcomes.values())
    names = [outcome["outcome"] for outcome in outcomes.values()]
    assert names.count("applied") == 1

    winner_label = next(
        label for label, outcome in outcomes.items() if outcome["outcome"] == "applied"
    )
    winning_group = winner_label.split("_", 1)[0]
    losing_group = "b" if winning_group == "a" else "a"

    winning_names = [outcomes[label]["outcome"] for label in group_labels[winning_group]]
    losing_names = [outcomes[label]["outcome"] for label in group_labels[losing_group]]
    assert winning_names.count("applied") == 1
    assert winning_names.count("idempotent") == multiplicities[winning_group] - 1
    assert all(name in {"applied", "idempotent"} for name in winning_names)
    assert losing_names == ["generation_reuse_rejected"] * multiplicities[losing_group]
    assert names.count("generation_reuse_rejected") == multiplicities[losing_group]

    for outcome in outcomes.values():
        assert outcome["fencing_version"] == pending_version
        assert outcome["resource_version"] == pending_version
        assert outcome["automatic_control_allowed"] is False
        assert outcome["activation_allowed"] is False
        assert outcome["traffic_switching_allowed"] is False

    recovered_expected = _expected_pair(
        counter=pending_counter,
        version=pending_version,
        mutation_id=mutation_ids[winning_group],
        value=values[winning_group],
    )
    _assert_committed_pair(database, long_lived_reader, recovered_expected)
    _assert_committed_pair(database, fresh_reader, recovered_expected)
    _assert_write_lock_released(database)

    replay_writer = SQLiteTransactionallyFencedProtectedResource(
        database, timeout_seconds=3.0
    )
    winner_replay = replay_writer.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        pending_counter,
        mutation_id=mutation_ids[winning_group],
        value=values[winning_group],
    )
    assert winner_replay.outcome == "idempotent"
    assert winner_replay.accepted is True
    assert winner_replay.state_changed is False
    assert winner_replay.fencing_version == pending_version
    assert winner_replay.resource_version == pending_version

    loser_replay = replay_writer.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        pending_counter,
        mutation_id=mutation_ids[losing_group],
        value=values[losing_group],
    )
    assert loser_replay.outcome == "generation_reuse_rejected"
    assert loser_replay.accepted is False
    assert loser_replay.state_changed is False
    assert loser_replay.fencing_version == pending_version
    assert loser_replay.resource_version == pending_version

    return (
        mutation_ids[winning_group],
        values[winning_group],
        recovered_expected,
    )


def test_alternating_duplicate_triplicate_groups_converge_once_per_generation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "alternating-group-multiplicity.sqlite3"
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

    prior_counter = current_counter
    prior_mutation_id = current_mutation_id
    prior_value = current_value

    for offset, triplicate_group in enumerate(("b", "a"), start=1):
        pending_counter = BASE_COUNTER + offset
        pending_version = 1 + offset
        winner_mutation_id, winner_value, current_expected = _run_multiplicity_generation(
            context=context,
            database=database,
            long_lived_reader=long_lived_reader,
            current_expected=current_expected,
            pending_counter=pending_counter,
            pending_version=pending_version,
            triplicate_group=triplicate_group,
        )

        stale = SQLiteTransactionallyFencedProtectedResource(
            database, timeout_seconds=3.0
        ).mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            prior_counter,
            mutation_id=prior_mutation_id,
            value=prior_value,
        )
        assert stale.outcome == "stale"
        assert stale.accepted is False
        assert stale.state_changed is False
        assert stale.fencing_version == pending_version
        assert stale.resource_version == pending_version

        prior_counter = pending_counter
        prior_mutation_id = winner_mutation_id
        prior_value = winner_value

    _assert_write_lock_released(database)

    successor_counter = BASE_COUNTER + 3
    successor = writer.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        successor_counter,
        mutation_id=f"mutation-{successor_counter}-successor",
        value=f"committed-{successor_counter}-successor",
    )
    assert successor.outcome == "applied"
    assert successor.accepted is True
    assert successor.state_changed is True
    assert successor.fencing_version == 4
    assert successor.resource_version == 4
    assert successor.automatic_control_allowed is False
    assert successor.activation_allowed is False
    assert successor.traffic_switching_allowed is False
    _assert_write_lock_released(database)


def test_alternating_group_multiplicity_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "power-loss" in combined
    assert "production readiness" in combined
    assert "performance" in combined
    assert "novelty" in combined
