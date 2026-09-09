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


BASE_COUNTER = 3401


def test_duplicate_and_conflicting_same_generation_waiters_converge_after_holder_loss(
    tmp_path: Path,
) -> None:
    database = tmp_path / "mixed-same-generation-waiter-convergence.sqlite3"
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
    duplicate_mutation_id = f"mutation-{pending_counter}-duplicate"
    duplicate_value = f"committed-{pending_counter}-duplicate"
    conflicting_mutation_id = f"mutation-{pending_counter}-conflict"
    conflicting_value = f"committed-{pending_counter}-conflict"

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
        name="mixed-same-generation-holder",
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

    duplicate_alpha, duplicate_alpha_results = _start_replacement_waiter(
        context,
        database,
        pending_counter=pending_counter,
        pending_mutation_id=duplicate_mutation_id,
        pending_value=duplicate_value,
        label="mixed-duplicate-alpha",
    )
    duplicate_beta, duplicate_beta_results = _start_replacement_waiter(
        context,
        database,
        pending_counter=pending_counter,
        pending_mutation_id=duplicate_mutation_id,
        pending_value=duplicate_value,
        label="mixed-duplicate-beta",
    )
    conflict, conflict_results = _start_replacement_waiter(
        context,
        database,
        pending_counter=pending_counter,
        pending_mutation_id=conflicting_mutation_id,
        pending_value=conflicting_value,
        label="mixed-conflict",
    )

    # E78 evidence gate: two waiters request one exact mutation while a third requests a
    # conflicting mutation at the same pending generation. All three are independently
    # reconstructed production writers. While the staged holder owns SQLite's transaction,
    # every waiter must remain blocked and the pending generation must remain invisible.
    assert duplicate_alpha.is_alive()
    assert duplicate_beta.is_alive()
    assert conflict.is_alive()
    assert holder.is_alive()
    _assert_committed_pair(database, long_lived_reader, current_expected)
    _assert_committed_pair(database, fresh_reader, current_expected)

    _terminate_holder(holder)

    outcomes = {
        "duplicate_alpha": duplicate_alpha_results.get(timeout=10.0),
        "duplicate_beta": duplicate_beta_results.get(timeout=10.0),
        "conflict": conflict_results.get(timeout=10.0),
    }
    _join_cleanly(duplicate_alpha, "duplicate alpha same-generation waiter")
    _join_cleanly(duplicate_beta, "duplicate beta same-generation waiter")
    _join_cleanly(conflict, "conflicting same-generation waiter")

    assert all(outcome["kind"] == "outcome" for outcome in outcomes.values())
    assert [outcome["outcome"] for outcome in outcomes.values()].count("applied") == 1

    applied_name = next(
        name for name, outcome in outcomes.items() if outcome["outcome"] == "applied"
    )
    if applied_name == "conflict":
        # If the conflicting logical mutation wins first, both instances of the other
        # logical mutation must fail closed because the generation has been consumed by
        # a different mutation identity/value.
        assert outcomes["duplicate_alpha"]["outcome"] == "generation_reuse_rejected"
        assert outcomes["duplicate_beta"]["outcome"] == "generation_reuse_rejected"
        winning_mutation_id = conflicting_mutation_id
        winning_value = conflicting_value
        losing_payloads = [(duplicate_mutation_id, duplicate_value)]
    else:
        # If either duplicate instance wins first, the second exact copy must converge via
        # idempotent replay while the logically conflicting mutation fails closed.
        other_duplicate = (
            "duplicate_beta" if applied_name == "duplicate_alpha" else "duplicate_alpha"
        )
        assert outcomes[other_duplicate]["outcome"] == "idempotent"
        assert outcomes["conflict"]["outcome"] == "generation_reuse_rejected"
        winning_mutation_id = duplicate_mutation_id
        winning_value = duplicate_value
        losing_payloads = [(conflicting_mutation_id, conflicting_value)]

    for name, outcome in outcomes.items():
        assert outcome["fencing_version"] == pending_version, name
        assert outcome["resource_version"] == pending_version, name
        assert outcome["automatic_control_allowed"] is False, name
        assert outcome["activation_allowed"] is False, name
        assert outcome["traffic_switching_allowed"] is False, name
        if outcome["outcome"] == "applied":
            assert outcome["accepted"] is True, name
            assert outcome["state_changed"] is True, name
        elif outcome["outcome"] == "idempotent":
            assert outcome["accepted"] is True, name
            assert outcome["state_changed"] is False, name
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

    verification_writer = SQLiteTransactionallyFencedProtectedResource(
        database, timeout_seconds=3.0
    )

    stale = verification_writer.mutate(
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

    for losing_mutation_id, losing_value in losing_payloads:
        losing_replay = verification_writer.mutate(
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

    winning_replay = verification_writer.mutate(
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

    _assert_committed_pair(database, long_lived_reader, recovered_expected)
    _assert_write_lock_released(database)

    successor_counter = pending_counter + 1
    successor = verification_writer.mutate(
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


def test_mixed_same_generation_waiter_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "power-loss" in combined
    assert "production readiness" in combined
    assert "performance" in combined
    assert "novelty" in combined
