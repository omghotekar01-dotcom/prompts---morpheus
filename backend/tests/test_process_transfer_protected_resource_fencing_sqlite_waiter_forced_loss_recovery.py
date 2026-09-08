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
from test_process_transfer_protected_resource_fencing_sqlite_mixed_contention_forced_loss import (
    AUTHORITY_ID,
    RESOURCE_ID,
    _assert_write_lock_released,
    _expected_pair,
    _pair_payload,
    _stage_uncommitted_next_generation,
)
from test_process_transfer_protected_resource_fencing_sqlite_mixed_timeout_waiter_recovery import (
    SHORT_TIMEOUT_SECONDS,
    WAITER_TIMEOUT_SECONDS,
    _contend_for_pending_generation,
    _join_cleanly,
)


BASE_COUNTER = 1301
ROUNDS = 2
SHORT_CONTENDERS = 2


def _terminate_blocked_waiter(waiter: mp.Process) -> None:
    assert waiter.is_alive()
    waiter.terminate()
    waiter.join(timeout=10.0)
    if waiter.is_alive():
        waiter.kill()
        waiter.join(timeout=10.0)
    assert not waiter.is_alive()
    assert waiter.exitcode is not None
    assert waiter.exitcode != 0


def test_blocked_waiter_loss_preserves_pending_generation_for_reconstructed_recovery(
    tmp_path: Path,
) -> None:
    database = tmp_path / "blocked-waiter-forced-loss-recovery.sqlite3"
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
        pending_mutation_id = f"mutation-{pending_counter}-waiter-loss-{round_index}"
        pending_value = f"committed-{pending_counter}-waiter-loss-{round_index}"

        ready = context.Queue()
        release = context.Event()
        short_results = context.Queue()
        waiter_results = context.Queue()

        short_children = [
            context.Process(
                target=_contend_for_pending_generation,
                args=(
                    str(database),
                    f"short-{contender_index}",
                    SHORT_TIMEOUT_SECONDS,
                    ready,
                    release,
                    short_results,
                    pending_counter,
                    pending_mutation_id,
                    pending_value,
                ),
            )
            for contender_index in range(SHORT_CONTENDERS)
        ]
        waiter = context.Process(
            target=_contend_for_pending_generation,
            args=(
                str(database),
                "waiter",
                WAITER_TIMEOUT_SECONDS,
                ready,
                release,
                waiter_results,
                pending_counter,
                pending_mutation_id,
                pending_value,
            ),
        )

        for child in short_children:
            child.start()
        waiter.start()
        assert {ready.get(timeout=10.0) for _ in range(SHORT_CONTENDERS + 1)} == {
            "short-0",
            "short-1",
            "waiter",
        }

        holder_ready = context.Queue()
        hold = context.Event()
        holder = context.Process(
            target=_stage_uncommitted_next_generation,
            args=(str(database), holder_ready, hold, pending_counter, pending_version),
        )
        holder.start()
        assert holder_ready.get(timeout=10.0) == {
            "counter": pending_counter,
            "version": pending_version,
        }
        assert holder.is_alive()

        # The staged generation is uncommitted and therefore invisible before contention.
        assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
        assert _pair_payload(
            SQLiteTransactionConsistentFencingResourceReader(
                database, timeout_seconds=3.0
            ).snapshot_pair(RESOURCE_ID, AUTHORITY_ID)
        ) == expected

        release.set()

        short_outcomes = [
            short_results.get(timeout=10.0) for _ in range(SHORT_CONTENDERS)
        ]
        for child in short_children:
            _join_cleanly(child, "short-timeout contender")

        assert {result["actor"] for result in short_outcomes} == {
            "short-0",
            "short-1",
        }
        assert all(result["kind"] == "sqlite-failure" for result in short_outcomes)
        assert all(
            "SQLite transactionally fenced protected-resource mutation failed"
            in result["message"]
            for result in short_outcomes
        )

        # The long-timeout writer is still blocked behind the holder after all short writers
        # have failed closed. Killing that blocked writer must not expose, consume, or mutate
        # the holder's uncommitted generation.
        assert holder.is_alive()
        assert waiter.is_alive()
        _terminate_blocked_waiter(waiter)
        assert holder.is_alive()
        assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
        assert _pair_payload(
            SQLiteTransactionConsistentFencingResourceReader(
                database, timeout_seconds=3.0
            ).snapshot_pair(RESOURCE_ID, AUTHORITY_ID)
        ) == expected

        # Once the holder is also terminated, a freshly reconstructed normal writer must be
        # able to commit exactly the generation that both the failed short writers and killed
        # blocked waiter attempted. No replacement generation is allocated.
        _terminate_holder(holder)
        _assert_write_lock_released(database)

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
            SQLiteTransactionConsistentFencingResourceReader(
                database, timeout_seconds=3.0
            ).snapshot_pair(RESOURCE_ID, AUTHORITY_ID)
        ) == expected

        stale = reconstructed_writer.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            previous_counter,
            mutation_id=previous_mutation_id,
            value=previous_value,
        )
        assert stale.outcome == "stale"
        assert stale.accepted is False
        assert stale.state_changed is False

        replay = reconstructed_writer.mutate(
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


def test_blocked_waiter_forced_loss_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "power-loss" in combined
    assert "production readiness" in combined
    assert "performance" in combined
    assert "novelty" in combined
