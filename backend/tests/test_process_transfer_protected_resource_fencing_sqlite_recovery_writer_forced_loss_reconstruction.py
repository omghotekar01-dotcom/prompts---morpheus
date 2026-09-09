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
    _contend_for_pending_generation,
    _join_cleanly,
)
from test_process_transfer_protected_resource_fencing_sqlite_replacement_waiter_forced_loss_recovery import (
    _fresh_pair,
)
from test_process_transfer_protected_resource_fencing_sqlite_waiter_forced_loss_recovery import (
    _terminate_blocked_waiter,
)


BASE_COUNTER = 1701
ROUNDS = 2
SHORT_TIMEOUT_SECONDS = 0.25
BLOCKED_TIMEOUT_SECONDS = 8.0
RELEASE_ORDERS = (
    ("short", "original"),
    ("original", "short"),
)


def test_recovery_writer_loss_preserves_pending_generation_for_fresh_reconstruction(
    tmp_path: Path,
) -> None:
    database = tmp_path / "recovery-writer-forced-loss-reconstruction.sqlite3"
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

    for round_index, release_order in enumerate(RELEASE_ORDERS, start=1):
        previous_counter = current_counter
        previous_mutation_id = current_mutation_id
        previous_value = current_value
        pending_counter = current_counter + 1
        pending_version = expected_version + 1
        pending_mutation_id = f"mutation-{pending_counter}-recovery-loss-{round_index}"
        pending_value = f"committed-{pending_counter}-recovery-loss-{round_index}"

        ready = context.Queue()
        short_release = context.Event()
        original_release = context.Event()
        short_result_queue = context.Queue()
        original_result_queue = context.Queue()
        short = context.Process(
            target=_contend_for_pending_generation,
            args=(
                str(database),
                "short",
                SHORT_TIMEOUT_SECONDS,
                ready,
                short_release,
                short_result_queue,
                pending_counter,
                pending_mutation_id,
                pending_value,
            ),
        )
        original = context.Process(
            target=_contend_for_pending_generation,
            args=(
                str(database),
                "original",
                BLOCKED_TIMEOUT_SECONDS,
                ready,
                original_release,
                original_result_queue,
                pending_counter,
                pending_mutation_id,
                pending_value,
            ),
        )
        short.start()
        original.start()
        assert {ready.get(timeout=10.0) for _ in range(2)} == {"short", "original"}

        holder_ready = context.Queue()
        holder_hold = context.Event()
        holder = context.Process(
            target=_stage_uncommitted_next_generation,
            args=(str(database), holder_ready, holder_hold, pending_counter, pending_version),
        )
        holder.start()
        assert holder_ready.get(timeout=10.0) == {
            "counter": pending_counter,
            "version": pending_version,
        }
        assert holder.is_alive()
        assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
        assert _fresh_pair(database) == expected

        releases = {"short": short_release, "original": original_release}
        for actor in release_order:
            releases[actor].set()
            assert holder.is_alive()
            assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
            assert _fresh_pair(database) == expected

        short_result = short_result_queue.get(timeout=10.0)
        _join_cleanly(short, "short recovery-loss waiter")
        assert short_result["actor"] == "short"
        assert short_result["kind"] == "sqlite-failure"
        assert "SQLite transactionally fenced protected-resource mutation failed" in short_result["message"]

        assert original.is_alive()
        _terminate_blocked_waiter(original)
        assert holder.is_alive()
        assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
        assert _fresh_pair(database) == expected

        replacement_ready = context.Queue()
        replacement_release = context.Event()
        replacement_result_queue = context.Queue()
        replacement = context.Process(
            target=_contend_for_pending_generation,
            args=(
                str(database),
                "replacement",
                BLOCKED_TIMEOUT_SECONDS,
                replacement_ready,
                replacement_release,
                replacement_result_queue,
                pending_counter,
                pending_mutation_id,
                pending_value,
            ),
        )
        replacement.start()
        assert replacement_ready.get(timeout=10.0) == "replacement"
        replacement_release.set()
        assert replacement.is_alive()
        assert holder.is_alive()
        assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
        assert _fresh_pair(database) == expected

        _terminate_blocked_waiter(replacement)
        assert holder.is_alive()
        assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
        assert _fresh_pair(database) == expected

        # Remove the original uncommitted owner after both non-owning waiters are lost.
        _terminate_holder(holder)
        _assert_write_lock_released(database)
        assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
        assert _fresh_pair(database) == expected

        # Reconstruct a recovery transaction actor for that exact pending generation and
        # deliberately lose it after both rows have been staged but before COMMIT.  This
        # deterministic staging helper exercises SQLite rollback-on-process-loss without
        # claiming that arbitrary production-adapter instruction boundaries are kill-safe.
        recovery_ready = context.Queue()
        recovery_hold = context.Event()
        recovery = context.Process(
            target=_stage_uncommitted_next_generation,
            args=(str(database), recovery_ready, recovery_hold, pending_counter, pending_version),
        )
        recovery.start()
        assert recovery_ready.get(timeout=10.0) == {
            "counter": pending_counter,
            "version": pending_version,
        }
        assert recovery.is_alive()
        assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
        assert _fresh_pair(database) == expected

        _terminate_holder(recovery)
        _assert_write_lock_released(database)
        assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
        assert _fresh_pair(database) == expected

        # A fresh production writer must still commit exactly that same pending generation;
        # the two waiter losses plus one staged recovery loss must not consume or skip it.
        recovery_writer = SQLiteTransactionallyFencedProtectedResource(
            database, timeout_seconds=3.0
        )
        recovered = recovery_writer.mutate(
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
        assert _fresh_pair(database) == expected
        _assert_write_lock_released(database)

        stale = recovery_writer.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            previous_counter,
            mutation_id=previous_mutation_id,
            value=previous_value,
        )
        assert stale.outcome == "stale"
        assert stale.accepted is False
        assert stale.state_changed is False

        replay = recovery_writer.mutate(
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
        assert _fresh_pair(database) == expected
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


def test_recovery_writer_forced_loss_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "power-loss" in combined
    assert "production readiness" in combined
    assert "performance" in combined
    assert "novelty" in combined
