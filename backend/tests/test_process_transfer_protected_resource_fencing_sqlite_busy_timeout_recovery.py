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
from test_process_transfer_protected_resource_fencing_sqlite_mixed_contention_forced_loss import (
    AUTHORITY_ID,
    RESOURCE_ID,
    _assert_write_lock_released,
    _expected_pair,
    _pair_payload,
    _stage_uncommitted_next_generation,
)


BASE_COUNTER = 1001
ROUNDS = 2


def _terminate_holder(child: mp.Process) -> None:
    assert child.is_alive()
    child.terminate()
    child.join(timeout=10.0)
    if child.is_alive():
        raise AssertionError("busy-timeout lock holder remained alive")
    assert child.exitcode is not None and child.exitcode != 0


def test_competing_writer_timeout_is_fail_closed_and_pending_generation_recovers(tmp_path: Path) -> None:
    database = tmp_path / "busy-timeout-recovery.sqlite3"
    writer = SQLiteTransactionallyFencedProtectedResource(database, timeout_seconds=3.0)
    long_lived_reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=3.0)
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
    expected_version = 1
    expected = _expected_pair(
        counter=current_counter,
        version=expected_version,
        mutation_id=current_mutation_id,
        value=current_value,
    )
    assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected

    for round_index in range(1, ROUNDS + 1):
        previous_counter = current_counter
        previous_mutation_id = current_mutation_id
        previous_value = current_value
        pending_counter = current_counter + 1
        pending_version = expected_version + 1
        pending_mutation_id = f"mutation-{pending_counter}-timeout-recovery"
        pending_value = f"committed-{pending_counter}-timeout-recovery"

        # Construct the independent contender before the holder acquires the write lock so
        # this gate specifically exercises mutate()/BEGIN IMMEDIATE busy-timeout behavior,
        # not constructor/schema-initialization contention.
        short_timeout_contender = SQLiteTransactionallyFencedProtectedResource(
            database, timeout_seconds=0.25
        )
        ready = context.Queue()
        hold = context.Event()
        holder = context.Process(
            target=_stage_uncommitted_next_generation,
            args=(str(database), ready, hold, pending_counter, pending_version),
        )
        holder.start()
        assert ready.get(timeout=10.0) == {
            "counter": pending_counter,
            "version": pending_version,
        }
        assert holder.is_alive()

        # The holder has staged a coherent next-generation pair but has not committed it.
        # Readers must continue seeing the previous committed pair while another writer
        # reaches its bounded SQLite busy timeout.
        assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
        assert _pair_payload(
            SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=3.0).snapshot_pair(
                RESOURCE_ID, AUTHORITY_ID
            )
        ) == expected

        with pytest.raises(
            ValueError,
            match="SQLite transactionally fenced protected-resource mutation failed",
        ):
            short_timeout_contender.mutate(
                RESOURCE_ID,
                AUTHORITY_ID,
                pending_counter,
                mutation_id=pending_mutation_id,
                value=pending_value,
            )

        # A timed-out contender must not expose or consume the staged generation.
        assert holder.is_alive()
        assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
        assert _pair_payload(
            SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=3.0).snapshot_pair(
                RESOURCE_ID, AUTHORITY_ID
            )
        ) == expected

        _terminate_holder(holder)
        _assert_write_lock_released(database)

        # After process loss releases the holder lock, reconstruct a normal-timeout writer
        # and apply exactly the generation that was staged and then blocked above.
        recovered_writer = SQLiteTransactionallyFencedProtectedResource(database, timeout_seconds=3.0)
        recovered = recovered_writer.mutate(
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

        current_counter = pending_counter
        current_mutation_id = pending_mutation_id
        current_value = pending_value
        expected_version = pending_version
        expected = _expected_pair(
            counter=current_counter,
            version=expected_version,
            mutation_id=current_mutation_id,
            value=current_value,
        )
        assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
        assert _pair_payload(
            SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=3.0).snapshot_pair(
                RESOURCE_ID, AUTHORITY_ID
            )
        ) == expected

        stale = recovered_writer.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            previous_counter,
            mutation_id=previous_mutation_id,
            value=previous_value,
        )
        assert stale.outcome == "stale"
        assert stale.accepted is False
        assert stale.state_changed is False

        replay = recovered_writer.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            current_counter,
            mutation_id=current_mutation_id,
            value=current_value,
        )
        assert replay.outcome == "idempotent"
        assert replay.accepted is True
        assert replay.state_changed is False
        assert replay.fencing_version == expected_version
        assert replay.resource_version == expected_version
        assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
        _assert_write_lock_released(database)

    successor_counter = current_counter + 1
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
    assert successor.fencing_version == expected_version + 1
    assert successor.resource_version == expected_version + 1
    assert successor.automatic_control_allowed is False
    assert successor.activation_allowed is False
    assert successor.traffic_switching_allowed is False
    _assert_write_lock_released(database)


def test_busy_timeout_recovery_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "power-loss" in combined
    assert "production readiness" in combined
    assert "performance" in combined
    assert "novelty" in combined
