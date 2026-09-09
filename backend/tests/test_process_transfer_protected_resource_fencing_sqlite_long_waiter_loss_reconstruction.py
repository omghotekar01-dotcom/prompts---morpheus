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
)
from test_process_transfer_protected_resource_fencing_sqlite_replacement_waiter_forced_loss_recovery import (
    _fresh_pair,
)


BASE_COUNTER = 2101
SHORT_TIMEOUT_BUDGETS_SECONDS = (0.20, 0.45)
LONG_WAITER_TIMEOUT_SECONDS = 5.0


def _assert_committed_pair(
    database: Path,
    reader: SQLiteTransactionConsistentFencingResourceReader,
    expected: dict[str, object],
) -> None:
    assert _pair_payload(reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
    assert _fresh_pair(database) == expected


def test_longer_timeout_waiter_loss_preserves_pending_generation_for_fresh_reconstruction(
    tmp_path: Path,
) -> None:
    database = tmp_path / "long-waiter-loss-reconstruction.sqlite3"
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

    current_version = 1
    current_expected = _expected_pair(
        counter=current_counter,
        version=current_version,
        mutation_id=current_mutation_id,
        value=current_value,
    )
    _assert_committed_pair(database, long_lived_reader, current_expected)

    pending_counter = current_counter + 1
    pending_version = current_version + 1
    pending_mutation_id = f"mutation-{pending_counter}-long-waiter-loss"
    pending_value = f"committed-{pending_counter}-long-waiter-loss"

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
        name="long-waiter-loss-staged-holder",
    )
    holder.start()
    assert holder_ready.get(timeout=10.0) == {
        "counter": pending_counter,
        "version": pending_version,
    }
    assert holder.is_alive()
    _assert_committed_pair(database, long_lived_reader, current_expected)

    # Distinct short busy-timeout budgets exercise fail-closed contention only. They are
    # deterministic test inputs, not scheduler, fairness, latency, or throughput claims.
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

    # Reconstruct a production waiter with a longer bounded timeout and release it while the
    # staged holder still owns the write transaction. The waiter must stay blocked and cannot
    # expose or consume uncommitted state.
    waiter_ready = context.Queue()
    waiter_release = context.Event()
    waiter_results = context.Queue()
    waiter = context.Process(
        target=_contend_for_pending_generation,
        args=(
            str(database),
            "long-waiter-to-lose",
            LONG_WAITER_TIMEOUT_SECONDS,
            waiter_ready,
            waiter_release,
            waiter_results,
            pending_counter,
            pending_mutation_id,
            pending_value,
        ),
        name="long-waiter-to-lose",
    )
    waiter.start()
    assert waiter_ready.get(timeout=10.0) == "long-waiter-to-lose"
    waiter_release.set()
    assert waiter.is_alive()
    assert holder.is_alive()
    _assert_committed_pair(database, long_lived_reader, current_expected)

    # Force loss of the non-owning blocked waiter before holder loss. This is bounded process
    # fault injection at a known blocked boundary; it is not arbitrary instruction-boundary
    # crash-safety evidence.
    _terminate_holder(waiter)
    assert holder.is_alive()
    _assert_committed_pair(database, long_lived_reader, current_expected)

    # Losing the waiter cannot consume, advance, or partially expose the pending generation.
    # After the staged holder is lost and SQLite rolls back that transaction, a fresh writer
    # must be able to commit exactly the same pending generation once.
    _terminate_holder(holder)
    _assert_write_lock_released(database)
    _assert_committed_pair(database, long_lived_reader, current_expected)

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


def test_long_waiter_loss_reconstruction_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "power-loss" in combined
    assert "production readiness" in combined
    assert "performance" in combined
    assert "novelty" in combined
