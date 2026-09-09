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
from test_process_transfer_protected_resource_fencing_sqlite_mixed_contention_forced_loss import (
    AUTHORITY_ID,
    RESOURCE_ID,
    _assert_write_lock_released,
    _expected_pair,
    _pair_payload,
    _stage_uncommitted_next_generation,
)
from test_process_transfer_protected_resource_fencing_sqlite_mixed_timeout_waiter_recovery import (
    _contend_for_pending_generation,
    _join_cleanly,
)
from test_process_transfer_protected_resource_fencing_sqlite_replacement_waiter_forced_loss_recovery import (
    _fresh_pair,
)


BASE_COUNTER = 2001
RECOVERY_LOSSES = 3
TIMEOUT_BUDGETS_SECONDS = (0.20, 0.45)
SURVIVING_WAITER_TIMEOUT_SECONDS = 5.0


def _assert_committed_pair(
    database: Path,
    reader: SQLiteTransactionConsistentFencingResourceReader,
    expected: dict[str, object],
) -> None:
    assert _pair_payload(reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
    assert _fresh_pair(database) == expected


def test_heterogeneous_timeout_contention_across_repeated_recovery_losses_preserves_generation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "heterogeneous-timeout-repeated-recovery-loss.sqlite3"
    writer = SQLiteTransactionallyFencedProtectedResource(database, timeout_seconds=3.0)
    long_lived_reader = SQLiteTransactionConsistentFencingResourceReader(
        database, timeout_seconds=3.0
    )
    context = mp.get_context("spawn")

    current_counter = BASE_COUNTER
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
    assert initial.automatic_control_allowed is False
    assert initial.activation_allowed is False
    assert initial.traffic_switching_allowed is False

    expected_version = 1
    expected = _expected_pair(
        counter=current_counter,
        version=expected_version,
        mutation_id=current_mutation_id,
        value=current_value,
    )
    _assert_committed_pair(database, long_lived_reader, expected)

    pending_counter = current_counter + 1
    pending_version = expected_version + 1
    pending_mutation_id = f"mutation-{pending_counter}-heterogeneous-timeout-recovery"
    pending_value = f"committed-{pending_counter}-heterogeneous-timeout-recovery"

    # Repeat one deterministic staged-but-uncommitted recovery boundary while production
    # writers use intentionally different bounded SQLite timeout budgets. These fixed budgets
    # are fault-injection mechanisms only; they do not establish scheduler fairness, bounded
    # waiting, arbitrary instruction-boundary kill safety, or production latency guarantees.
    for loss_index in range(1, RECOVERY_LOSSES + 1):
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
            name=f"heterogeneous-timeout-recovery-loss-{loss_index}",
        )
        recovery.start()
        assert recovery_ready.get(timeout=10.0) == {
            "counter": pending_counter,
            "version": pending_version,
        }
        assert recovery.is_alive()
        _assert_committed_pair(database, long_lived_reader, expected)

        # Every contender whose bounded timeout expires before holder loss must fail closed.
        # The distinct budgets exercise heterogeneous timeout configuration against the same
        # staged generation without claiming any ordering/fairness property between writers.
        for contender_index, timeout_seconds in enumerate(
            TIMEOUT_BUDGETS_SECONDS, start=1
        ):
            contender = SQLiteTransactionallyFencedProtectedResource(
                database,
                timeout_seconds=timeout_seconds,
            )
            with pytest.raises(
                ValueError,
                match="SQLite transactionally fenced protected-resource mutation failed",
            ):
                contender.mutate(
                    RESOURCE_ID,
                    AUTHORITY_ID,
                    pending_counter,
                    mutation_id=(
                        f"{pending_mutation_id}-loss-{loss_index}-"
                        f"timeout-{contender_index}"
                    ),
                    value=f"{pending_value}-timeout-{contender_index}",
                )

            assert recovery.is_alive()
            _assert_committed_pair(database, long_lived_reader, expected)

        if loss_index < RECOVERY_LOSSES:
            _terminate_holder(recovery)
            _assert_write_lock_released(database)
            _assert_committed_pair(database, long_lived_reader, expected)
            continue

        # On the final cycle, reconstruct a longer-timeout production waiter while the same
        # uncommitted recovery transaction still owns the lock. It must remain blocked until
        # holder loss and must not observe or consume staged state beforehand.
        waiter_ready = context.Queue()
        waiter_release = context.Event()
        waiter_results = context.Queue()
        waiter = context.Process(
            target=_contend_for_pending_generation,
            args=(
                str(database),
                "surviving-waiter",
                SURVIVING_WAITER_TIMEOUT_SECONDS,
                waiter_ready,
                waiter_release,
                waiter_results,
                pending_counter,
                pending_mutation_id,
                pending_value,
            ),
            name="heterogeneous-timeout-surviving-waiter",
        )
        waiter.start()
        assert waiter_ready.get(timeout=10.0) == "surviving-waiter"
        waiter_release.set()
        assert recovery.is_alive()
        assert waiter.is_alive()
        _assert_committed_pair(database, long_lived_reader, expected)

        # Holder loss rolls back the staged transaction. The already-waiting production
        # writer may then serialize exactly one commit of the unchanged pending generation.
        _terminate_holder(recovery)
        waiter_outcome = waiter_results.get(timeout=10.0)
        _join_cleanly(waiter, "heterogeneous-timeout surviving waiter")

        assert waiter_outcome["actor"] == "surviving-waiter"
        assert waiter_outcome["kind"] == "outcome"
        assert waiter_outcome["outcome"] == "applied"
        assert waiter_outcome["accepted"] is True
        assert waiter_outcome["state_changed"] is True
        assert waiter_outcome["fencing_version"] == pending_version
        assert waiter_outcome["resource_version"] == pending_version
        assert waiter_outcome["automatic_control_allowed"] is False
        assert waiter_outcome["activation_allowed"] is False
        assert waiter_outcome["traffic_switching_allowed"] is False

    recovered_expected = _expected_pair(
        counter=pending_counter,
        version=pending_version,
        mutation_id=pending_mutation_id,
        value=pending_value,
    )
    _assert_committed_pair(database, long_lived_reader, recovered_expected)
    _assert_write_lock_released(database)

    reconstructed_writer = SQLiteTransactionallyFencedProtectedResource(
        database, timeout_seconds=3.0
    )
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
    _assert_write_lock_released(database)

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


def test_heterogeneous_timeout_repeated_recovery_loss_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "power-loss" in combined
    assert "production readiness" in combined
    assert "performance" in combined
    assert "novelty" in combined
