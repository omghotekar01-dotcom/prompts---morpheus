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
from test_process_transfer_protected_resource_fencing_sqlite_waiter_forced_loss_recovery import (
    _terminate_blocked_waiter,
)


BASE_COUNTER = 1501
ROUNDS = 3
SHORT_TIMEOUT_SECONDS = 0.25
ORIGINAL_TIMEOUT_SECONDS = 8.0
REPLACEMENT_TIMEOUT_SECONDS = 8.0
RELEASE_ORDERS = (
    ("short", "original"),
    ("original", "short"),
    ("short", "original"),
)


def _fresh_pair(database: Path) -> dict[str, object]:
    return _pair_payload(
        SQLiteTransactionConsistentFencingResourceReader(
            database, timeout_seconds=3.0
        ).snapshot_pair(RESOURCE_ID, AUTHORITY_ID)
    )


def test_waiter_replacement_preserves_pending_generation_and_recovers_once(
    tmp_path: Path,
) -> None:
    database = tmp_path / "waiter-replacement-recovery.sqlite3"
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
        pending_mutation_id = f"mutation-{pending_counter}-replacement-{round_index}"
        pending_value = f"committed-{pending_counter}-replacement-{round_index}"

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
                ORIGINAL_TIMEOUT_SECONDS,
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
        assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
        assert _fresh_pair(database) == expected

        releases = {"short": short_release, "original": original_release}
        for actor in release_order:
            releases[actor].set()
            assert holder.is_alive()
            assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
            assert _fresh_pair(database) == expected

        short_result = short_result_queue.get(timeout=10.0)
        _join_cleanly(short, "short replacement-gate waiter")
        assert short_result["actor"] == "short"
        assert short_result["kind"] == "sqlite-failure"
        assert (
            "SQLite transactionally fenced protected-resource mutation failed"
            in short_result["message"]
        )

        # The originally designated long-timeout recovery waiter is still blocked and
        # non-owning. Losing it must not expose or consume the holder's staged generation.
        assert original.is_alive()
        _terminate_blocked_waiter(original)
        assert holder.is_alive()
        assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
        assert _fresh_pair(database) == expected

        # Reconstruct a new writer only after the original waiter has been lost, while the
        # holder still owns the uncommitted transaction. The replacement must itself remain
        # blocked and non-mutating until holder loss.
        replacement_ready = context.Queue()
        replacement_release = context.Event()
        replacement_result_queue = context.Queue()
        replacement = context.Process(
            target=_contend_for_pending_generation,
            args=(
                str(database),
                "replacement",
                REPLACEMENT_TIMEOUT_SECONDS,
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

        # Only after the replacement has entered contention do we remove the holder. The
        # replacement must commit the exact still-pending generation once rather than skip it.
        _terminate_holder(holder)
        replacement_result = replacement_result_queue.get(timeout=10.0)
        _join_cleanly(replacement, "replacement recovery waiter")
        assert replacement_result["actor"] == "replacement"
        assert replacement_result["kind"] == "outcome"
        assert replacement_result["outcome"] == "applied"
        assert replacement_result["accepted"] is True
        assert replacement_result["state_changed"] is True
        assert replacement_result["fencing_version"] == pending_version
        assert replacement_result["resource_version"] == pending_version
        assert replacement_result["automatic_control_allowed"] is False
        assert replacement_result["activation_allowed"] is False
        assert replacement_result["traffic_switching_allowed"] is False

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

        reconstructed_writer = SQLiteTransactionallyFencedProtectedResource(
            database, timeout_seconds=3.0
        )
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


def test_waiter_replacement_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "power-loss" in combined
    assert "production readiness" in combined
    assert "performance" in combined
    assert "novelty" in combined
