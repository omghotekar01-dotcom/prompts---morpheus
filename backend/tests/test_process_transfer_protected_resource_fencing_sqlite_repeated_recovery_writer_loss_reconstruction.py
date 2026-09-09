from __future__ import annotations

import multiprocessing as mp
from pathlib import Path

import pytest

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
    SHORT_TIMEOUT_BUDGETS_SECONDS,
    _assert_committed_pair,
)
from test_process_transfer_protected_resource_fencing_sqlite_mixed_contention_forced_loss import (
    AUTHORITY_ID,
    RESOURCE_ID,
    _assert_write_lock_released,
    _expected_pair,
    _stage_uncommitted_next_generation,
)
from test_process_transfer_protected_resource_fencing_sqlite_replacement_long_waiter_loss_reconstruction import (
    _start_blocked_waiter,
)


BASE_COUNTER = 2401
RECOVERY_LOSS_COUNT = 3


def test_repeated_recovery_writer_losses_preserve_one_pending_generation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "repeated-recovery-writer-loss.sqlite3"
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
    pending_mutation_id = f"mutation-{pending_counter}-repeated-recovery-loss"
    pending_value = f"committed-{pending_counter}-repeated-recovery-loss"

    holder_ready = context.Queue()
    holder_hold = context.Event()
    holder = context.Process(
        target=_stage_uncommitted_next_generation,
        args=(
            str(database),
            holder_ready,
            holder_hold,
            pending_counter,
            pending_version,
        ),
        name="repeated-recovery-loss-original-holder",
    )
    holder.start()
    assert holder_ready.get(timeout=10.0) == {
        "counter": pending_counter,
        "version": pending_version,
    }
    assert holder.is_alive()
    _assert_committed_pair(database, long_lived_reader, current_expected)

    # These heterogeneous short timeout budgets are bounded contention inputs only. Their
    # failure does not establish fairness, scheduler behavior, or latency guarantees.
    for contender_index, timeout_seconds in enumerate(
        SHORT_TIMEOUT_BUDGETS_SECONDS, start=1
    ):
        contender = SQLiteTransactionallyFencedProtectedResource(
            database, timeout_seconds=timeout_seconds
        )
        with pytest.raises(
            ValueError,
            match="SQLite transactionally fenced protected-resource mutation failed",
        ):
            contender.mutate(
                RESOURCE_ID,
                AUTHORITY_ID,
                pending_counter,
                mutation_id=f"{pending_mutation_id}-short-{contender_index}",
                value=f"{pending_value}-short-{contender_index}",
            )
        assert holder.is_alive()
        _assert_committed_pair(database, long_lived_reader, current_expected)

    original_waiter = _start_blocked_waiter(
        context,
        database,
        name="original-long-waiter-before-repeated-recovery-loss",
        pending_counter=pending_counter,
        pending_mutation_id=pending_mutation_id,
        pending_value=pending_value,
    )
    assert holder.is_alive()
    _assert_committed_pair(database, long_lived_reader, current_expected)
    _terminate_holder(original_waiter)
    assert holder.is_alive()
    _assert_committed_pair(database, long_lived_reader, current_expected)

    replacement_waiter = _start_blocked_waiter(
        context,
        database,
        name="replacement-long-waiter-before-repeated-recovery-loss",
        pending_counter=pending_counter,
        pending_mutation_id=pending_mutation_id,
        pending_value=pending_value,
    )
    assert holder.is_alive()
    _assert_committed_pair(database, long_lived_reader, current_expected)
    _terminate_holder(replacement_waiter)
    assert holder.is_alive()
    _assert_committed_pair(database, long_lived_reader, current_expected)

    # Only after both non-owning waiters are gone do we lose the original staged owner. SQLite
    # must roll that known uncommitted transaction back without consuming the pending generation.
    _terminate_holder(holder)
    _assert_write_lock_released(database)
    _assert_committed_pair(database, long_lived_reader, current_expected)

    # Reconstruct and lose the exact same pending generation repeatedly. Every forced loss occurs
    # at the deterministic staged-but-uncommitted boundary exposed by the existing test helper.
    # This is bounded rollback evidence only, not arbitrary instruction-boundary kill safety.
    for recovery_index in range(1, RECOVERY_LOSS_COUNT + 1):
        recovery_ready = context.Queue()
        recovery_hold = context.Event()
        recovery = context.Process(
            target=_stage_uncommitted_next_generation,
            args=(
                str(database),
                recovery_ready,
                recovery_hold,
                pending_counter,
                pending_version,
            ),
            name=f"same-generation-recovery-writer-loss-{recovery_index}",
        )
        recovery.start()
        assert recovery_ready.get(timeout=10.0) == {
            "counter": pending_counter,
            "version": pending_version,
        }
        assert recovery.is_alive()
        _assert_committed_pair(database, long_lived_reader, current_expected)

        # Fresh-reader reconstruction must agree with the long-lived reader while the recovery
        # transaction owns staged state that has not committed.
        fresh_reader = SQLiteTransactionConsistentFencingResourceReader(
            database, timeout_seconds=3.0
        )
        _assert_committed_pair(database, fresh_reader, current_expected)

        _terminate_holder(recovery)
        _assert_write_lock_released(database)
        _assert_committed_pair(database, long_lived_reader, current_expected)
        _assert_committed_pair(database, fresh_reader, current_expected)

    # All repeated staged losses must leave the exact pending generation available. A freshly
    # reconstructed production writer is allowed to commit that generation exactly once.
    reconstructed_writer = SQLiteTransactionallyFencedProtectedResource(
        database, timeout_seconds=3.0
    )
    recovered = reconstructed_writer.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        pending_counter,
        mutation_id=pending_mutation_id,
        value=pending_value,
    )
    assert recovered.outcome == "applied"
    assert recovered.accepted is True
    assert recovered.state_changed is True
    assert recovered.fencing_version == pending_version
    assert recovered.resource_version == pending_version
    assert recovered.automatic_control_allowed is False
    assert recovered.activation_allowed is False
    assert recovered.traffic_switching_allowed is False

    recovered_expected = _expected_pair(
        counter=pending_counter,
        version=pending_version,
        mutation_id=pending_mutation_id,
        value=pending_value,
    )
    _assert_committed_pair(database, long_lived_reader, recovered_expected)
    _assert_write_lock_released(database)

    stale = reconstructed_writer.mutate(
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

    replay = reconstructed_writer.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        pending_counter,
        mutation_id=pending_mutation_id,
        value=pending_value,
    )
    assert replay.outcome == "idempotent"
    assert replay.accepted is True
    assert replay.state_changed is False
    assert replay.fencing_version == pending_version
    assert replay.resource_version == pending_version
    assert replay.automatic_control_allowed is False
    assert replay.activation_allowed is False
    assert replay.traffic_switching_allowed is False
    _assert_committed_pair(database, long_lived_reader, recovered_expected)

    successor_counter = pending_counter + 1
    successor = reconstructed_writer.mutate(
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


def test_repeated_recovery_writer_loss_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "power-loss" in combined
    assert "production readiness" in combined
    assert "performance" in combined
    assert "novelty" in combined
