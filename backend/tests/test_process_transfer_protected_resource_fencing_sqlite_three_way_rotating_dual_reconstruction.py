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
from test_process_transfer_protected_resource_fencing_sqlite_partial_duplicate_group_waiter_loss import (
    _terminate_waiter,
)
from test_process_transfer_protected_resource_fencing_sqlite_three_way_rotating_cardinality_reconstruction import (
    CARDINALITY_ROTATION,
)


BASE_COUNTER = 5601


def test_three_way_rotating_cardinality_survives_two_group_member_reconstruction(
    tmp_path: Path,
) -> None:
    database = tmp_path / "three-way-rotating-dual-reconstruction.sqlite3"
    writer = SQLiteTransactionallyFencedProtectedResource(database, timeout_seconds=3.0)
    long_lived_reader = SQLiteTransactionConsistentFencingResourceReader(
        database, timeout_seconds=3.0
    )
    context = mp.get_context("spawn")

    initial = writer.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        BASE_COUNTER,
        mutation_id=f"mutation-{BASE_COUNTER}",
        value=f"committed-{BASE_COUNTER}",
    )
    assert initial.outcome == "applied"
    assert initial.accepted is True
    assert initial.state_changed is True
    assert initial.fencing_version == 1
    assert initial.resource_version == 1
    assert initial.automatic_control_allowed is False
    assert initial.activation_allowed is False
    assert initial.traffic_switching_allowed is False

    current_expected = _expected_pair(
        counter=BASE_COUNTER,
        version=1,
        mutation_id=f"mutation-{BASE_COUNTER}",
        value=f"committed-{BASE_COUNTER}",
    )
    _assert_committed_pair(database, long_lived_reader, current_expected)

    previous_counter = BASE_COUNTER
    previous_mutation_id = f"mutation-{BASE_COUNTER}"
    previous_value = f"committed-{BASE_COUNTER}"

    for round_index, group_sizes in enumerate(CARDINALITY_ROTATION, start=1):
        pending_counter = BASE_COUNTER + round_index
        pending_version = round_index + 1
        perturbed_groups = [group for group, size in group_sizes.items() if size > 1]
        assert len(perturbed_groups) == 2

        ready = context.Queue()
        hold = context.Event()
        holder = context.Process(
            target=_stage_uncommitted_next_generation,
            args=(str(database), ready, hold, pending_counter, pending_version),
            name=f"three-way-rotating-dual-reconstruction-holder-{round_index}",
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

        mutation_ids = {
            group: f"mutation-{pending_counter}-{group}" for group in group_sizes
        }
        values = {
            group: f"committed-{pending_counter}-{group}" for group in group_sizes
        }

        waiters: dict[str, mp.Process] = {}
        result_queues = {}
        group_labels: dict[str, list[str]] = {group: [] for group in group_sizes}

        for group, group_size in group_sizes.items():
            for index in range(1, group_size + 1):
                label = f"{group}_{index}"
                process, results = _start_waiter(
                    context,
                    database,
                    counter=pending_counter,
                    mutation_id=mutation_ids[group],
                    value=values[group],
                    label=(
                        f"three-way-rotating-dual-reconstruction-"
                        f"{round_index}-{group}-{index}"
                    ),
                )
                waiters[label] = process
                result_queues[label] = results
                group_labels[group].append(label)

        assert len(waiters) == 6
        assert all(process.is_alive() for process in waiters.values())
        assert holder.is_alive()
        _assert_committed_pair(database, long_lived_reader, current_expected)
        _assert_committed_pair(database, fresh_reader, current_expected)

        for group in perturbed_groups:
            lost_label = group_labels[group][0]
            lost_process = waiters.pop(lost_label)
            result_queues.pop(lost_label)
            group_labels[group].remove(lost_label)
            _terminate_waiter(
                lost_process,
                f"round {round_index} blocked member from mutation {group}",
            )

            replacement_label = f"{group}_replacement"
            replacement, replacement_results = _start_waiter(
                context,
                database,
                counter=pending_counter,
                mutation_id=mutation_ids[group],
                value=values[group],
                label=(
                    f"three-way-rotating-dual-reconstruction-"
                    f"{round_index}-{group}-replacement"
                ),
            )
            waiters[replacement_label] = replacement
            result_queues[replacement_label] = replacement_results
            group_labels[group].append(replacement_label)

            assert len(group_labels[group]) == group_sizes[group]
            assert replacement.is_alive()
            assert holder.is_alive()
            _assert_committed_pair(database, long_lived_reader, current_expected)
            _assert_committed_pair(database, fresh_reader, current_expected)

        assert len(waiters) == 6
        assert all(process.is_alive() for process in waiters.values())
        assert holder.is_alive()
        _assert_committed_pair(database, long_lived_reader, current_expected)
        _assert_committed_pair(database, fresh_reader, current_expected)

        _terminate_holder(holder)

        outcomes = {
            label: result_queues[label].get(timeout=10.0) for label in waiters
        }
        for label, process in waiters.items():
            _join_cleanly(
                process,
                f"three-way rotating dual reconstruction waiter round {round_index} {label}",
            )

        assert all(outcome["kind"] == "outcome" for outcome in outcomes.values())
        names = [outcome["outcome"] for outcome in outcomes.values()]
        assert names.count("applied") == 1

        winner_label = next(
            label
            for label, outcome in outcomes.items()
            if outcome["outcome"] == "applied"
        )
        winning_group = winner_label.split("_", 1)[0]
        losing_groups = [group for group in group_sizes if group != winning_group]
        winning_size = group_sizes[winning_group]

        assert names.count("idempotent") == winning_size - 1
        assert names.count("generation_reuse_rejected") == 6 - winning_size

        winning_names = [
            outcomes[label]["outcome"] for label in group_labels[winning_group]
        ]
        assert winning_names.count("applied") == 1
        assert winning_names.count("idempotent") == winning_size - 1

        for group in losing_groups:
            losing_names = [outcomes[label]["outcome"] for label in group_labels[group]]
            assert losing_names == ["generation_reuse_rejected"] * group_sizes[group]

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

        for group in losing_groups:
            loser_replay = replay_writer.mutate(
                RESOURCE_ID,
                AUTHORITY_ID,
                pending_counter,
                mutation_id=mutation_ids[group],
                value=values[group],
            )
            assert loser_replay.outcome == "generation_reuse_rejected"
            assert loser_replay.accepted is False
            assert loser_replay.state_changed is False
            assert loser_replay.fencing_version == pending_version
            assert loser_replay.resource_version == pending_version

        stale = replay_writer.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            previous_counter,
            mutation_id=previous_mutation_id,
            value=previous_value,
        )
        assert stale.outcome == "stale"
        assert stale.accepted is False
        assert stale.state_changed is False
        assert stale.fencing_version == pending_version
        assert stale.resource_version == pending_version

        current_expected = recovered_expected
        previous_counter = pending_counter
        previous_mutation_id = mutation_ids[winning_group]
        previous_value = values[winning_group]

    successor_counter = BASE_COUNTER + len(CARDINALITY_ROTATION) + 1
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
    assert successor.fencing_version == len(CARDINALITY_ROTATION) + 2
    assert successor.resource_version == len(CARDINALITY_ROTATION) + 2
    assert successor.automatic_control_allowed is False
    assert successor.activation_allowed is False
    assert successor.traffic_switching_allowed is False
    _assert_write_lock_released(database)


def test_three_way_rotating_dual_reconstruction_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "power-loss" in combined
    assert "production readiness" in combined
    assert "performance" in combined
    assert "novelty" in combined
