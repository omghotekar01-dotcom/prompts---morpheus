from __future__ import annotations

import itertools
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


GROUPS = ("A", "B", "C")
CARDINALITY_ASSIGNMENTS = tuple(
    dict(zip(GROUPS, sizes, strict=True))
    for sizes in itertools.permutations((1, 2, 3))
)
BASE_COUNTER = 5701


def test_three_way_dual_reconstruction_is_invariant_to_identity_cardinality_assignment(
    tmp_path: Path,
) -> None:
    assert len(CARDINALITY_ASSIGNMENTS) == 6
    assert {
        tuple(assignment[group] for group in GROUPS)
        for assignment in CARDINALITY_ASSIGNMENTS
    } == set(itertools.permutations((1, 2, 3)))

    context = mp.get_context("spawn")

    for assignment_index, group_sizes in enumerate(CARDINALITY_ASSIGNMENTS, start=1):
        database = tmp_path / f"three-way-identity-permutation-{assignment_index}.sqlite3"
        writer = SQLiteTransactionallyFencedProtectedResource(database, timeout_seconds=3.0)
        long_lived_reader = SQLiteTransactionConsistentFencingResourceReader(
            database, timeout_seconds=3.0
        )

        initial_mutation_id = f"mutation-{BASE_COUNTER}"
        initial_value = f"committed-{BASE_COUNTER}"
        initial = writer.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            BASE_COUNTER,
            mutation_id=initial_mutation_id,
            value=initial_value,
        )
        assert initial.outcome == "applied"
        assert initial.accepted is True
        assert initial.state_changed is True
        assert initial.fencing_version == 1
        assert initial.resource_version == 1
        assert initial.automatic_control_allowed is False
        assert initial.activation_allowed is False
        assert initial.traffic_switching_allowed is False

        baseline_expected = _expected_pair(
            counter=BASE_COUNTER,
            version=1,
            mutation_id=initial_mutation_id,
            value=initial_value,
        )
        _assert_committed_pair(database, long_lived_reader, baseline_expected)

        pending_counter = BASE_COUNTER + 1
        pending_version = 2
        ready = context.Queue()
        hold = context.Event()
        holder = context.Process(
            target=_stage_uncommitted_next_generation,
            args=(str(database), ready, hold, pending_counter, pending_version),
            name=f"three-way-identity-permutation-holder-{assignment_index}",
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
        _assert_committed_pair(database, long_lived_reader, baseline_expected)
        _assert_committed_pair(database, fresh_reader, baseline_expected)

        mutation_ids = {
            group: f"mutation-{pending_counter}-{group}" for group in GROUPS
        }
        values = {
            group: f"committed-{pending_counter}-{group}" for group in GROUPS
        }
        waiters: dict[str, mp.Process] = {}
        result_queues = {}
        group_labels: dict[str, list[str]] = {group: [] for group in GROUPS}

        for group in GROUPS:
            for member_index in range(1, group_sizes[group] + 1):
                label = f"{group}_{member_index}"
                process, results = _start_waiter(
                    context,
                    database,
                    counter=pending_counter,
                    mutation_id=mutation_ids[group],
                    value=values[group],
                    label=(
                        "three-way-identity-permutation-"
                        f"{assignment_index}-{group}-{member_index}"
                    ),
                )
                waiters[label] = process
                result_queues[label] = results
                group_labels[group].append(label)

        assert len(waiters) == 6
        assert all(process.is_alive() for process in waiters.values())
        assert holder.is_alive()
        _assert_committed_pair(database, long_lived_reader, baseline_expected)
        _assert_committed_pair(database, fresh_reader, baseline_expected)

        reconstructed_groups = [group for group in GROUPS if group_sizes[group] > 1]
        assert len(reconstructed_groups) == 2

        for group in reconstructed_groups:
            lost_label = group_labels[group][0]
            lost_process = waiters.pop(lost_label)
            result_queues.pop(lost_label)
            group_labels[group].remove(lost_label)
            _terminate_waiter(
                lost_process,
                (
                    f"identity permutation {assignment_index} blocked member "
                    f"from mutation {group}"
                ),
            )

            replacement_label = f"{group}_replacement"
            replacement, replacement_results = _start_waiter(
                context,
                database,
                counter=pending_counter,
                mutation_id=mutation_ids[group],
                value=values[group],
                label=(
                    "three-way-identity-permutation-"
                    f"{assignment_index}-{group}-replacement"
                ),
            )
            waiters[replacement_label] = replacement
            result_queues[replacement_label] = replacement_results
            group_labels[group].append(replacement_label)

            assert len(group_labels[group]) == group_sizes[group]
            assert replacement.is_alive()
            assert holder.is_alive()
            _assert_committed_pair(database, long_lived_reader, baseline_expected)
            _assert_committed_pair(database, fresh_reader, baseline_expected)

        assert len(waiters) == 6
        assert all(process.is_alive() for process in waiters.values())
        assert holder.is_alive()
        _assert_committed_pair(database, long_lived_reader, baseline_expected)
        _assert_committed_pair(database, fresh_reader, baseline_expected)

        _terminate_holder(holder)

        outcomes = {
            label: result_queues[label].get(timeout=10.0) for label in waiters
        }
        for label, process in waiters.items():
            _join_cleanly(
                process,
                f"three-way identity permutation waiter {assignment_index} {label}",
            )

        assert all(outcome["kind"] == "outcome" for outcome in outcomes.values())
        outcome_names = [outcome["outcome"] for outcome in outcomes.values()]
        assert outcome_names.count("applied") == 1

        winner_label = next(
            label
            for label, outcome in outcomes.items()
            if outcome["outcome"] == "applied"
        )
        winning_group = winner_label.split("_", 1)[0]
        losing_groups = [group for group in GROUPS if group != winning_group]
        winning_size = group_sizes[winning_group]

        assert outcome_names.count("idempotent") == winning_size - 1
        assert outcome_names.count("generation_reuse_rejected") == 6 - winning_size

        winning_names = [
            outcomes[label]["outcome"] for label in group_labels[winning_group]
        ]
        assert winning_names.count("applied") == 1
        assert winning_names.count("idempotent") == winning_size - 1

        for group in losing_groups:
            losing_names = [
                outcomes[label]["outcome"] for label in group_labels[group]
            ]
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
            BASE_COUNTER,
            mutation_id=initial_mutation_id,
            value=initial_value,
        )
        assert stale.outcome == "stale"
        assert stale.accepted is False
        assert stale.state_changed is False
        assert stale.fencing_version == pending_version
        assert stale.resource_version == pending_version

        successor_counter = BASE_COUNTER + 2
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
        assert successor.fencing_version == 3
        assert successor.resource_version == 3
        assert successor.automatic_control_allowed is False
        assert successor.activation_allowed is False
        assert successor.traffic_switching_allowed is False
        _assert_write_lock_released(database)


def test_three_way_identity_permutation_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "power-loss" in combined
    assert "production readiness" in combined
    assert "performance" in combined
    assert "novelty" in combined
