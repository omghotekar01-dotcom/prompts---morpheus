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


BASE_COUNTER = 1401
ROUNDS = 3
TIMEOUT_SECONDS = {
    "short": 0.25,
    "killed": 5.0,
    "survivor": 8.0,
}
RELEASE_ORDERS = (
    ("short", "killed", "survivor"),
    ("killed", "survivor", "short"),
    ("survivor", "short", "killed"),
)


def _fresh_pair(database: Path) -> dict[str, object]:
    return _pair_payload(
        SQLiteTransactionConsistentFencingResourceReader(
            database, timeout_seconds=3.0
        ).snapshot_pair(RESOURCE_ID, AUTHORITY_ID)
    )


def test_heterogeneous_waiter_ordering_preserves_pending_generation_and_recovers_once(
    tmp_path: Path,
) -> None:
    database = tmp_path / "heterogeneous-waiter-ordering-recovery.sqlite3"
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
        pending_mutation_id = f"mutation-{pending_counter}-heterogeneous-{round_index}"
        pending_value = f"committed-{pending_counter}-heterogeneous-{round_index}"

        ready = context.Queue()
        result_queues = {actor: context.Queue() for actor in TIMEOUT_SECONDS}
        releases = {actor: context.Event() for actor in TIMEOUT_SECONDS}
        children = {
            actor: context.Process(
                target=_contend_for_pending_generation,
                args=(
                    str(database),
                    actor,
                    timeout_seconds,
                    ready,
                    releases[actor],
                    result_queues[actor],
                    pending_counter,
                    pending_mutation_id,
                    pending_value,
                ),
            )
            for actor, timeout_seconds in TIMEOUT_SECONDS.items()
        }

        for child in children.values():
            child.start()
        assert {ready.get(timeout=10.0) for _ in children} == set(children)

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

        # Vary which reconstructed waiter enters SQLite first in each round. The holder keeps
        # the write transaction owned throughout, so release order must not expose or consume
        # its uncommitted generation.
        for actor in release_order:
            releases[actor].set()
            assert holder.is_alive()
            assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
            assert _fresh_pair(database) == expected

        short_result = result_queues["short"].get(timeout=10.0)
        _join_cleanly(children["short"], "short heterogeneous waiter")
        assert short_result["actor"] == "short"
        assert short_result["kind"] == "sqlite-failure"
        assert (
            "SQLite transactionally fenced protected-resource mutation failed"
            in short_result["message"]
        )

        # The two longer-budget writers must still be non-owning waiters after the short
        # timeout. Terminating one such waiter must remain non-mutating while another waiter
        # stays available as the recovery path.
        assert children["killed"].is_alive()
        assert children["survivor"].is_alive()
        _terminate_blocked_waiter(children["killed"])
        assert holder.is_alive()
        assert children["survivor"].is_alive()
        assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
        assert _fresh_pair(database) == expected

        # Once the uncommitted holder is lost, the already-waiting survivor is the only live
        # contender. It must commit the exact still-pending generation once, independent of
        # the release ordering exercised in this round.
        _terminate_holder(holder)
        survivor_result = result_queues["survivor"].get(timeout=10.0)
        _join_cleanly(children["survivor"], "surviving heterogeneous waiter")
        assert survivor_result["actor"] == "survivor"
        assert survivor_result["kind"] == "outcome"
        assert survivor_result["outcome"] == "applied"
        assert survivor_result["accepted"] is True
        assert survivor_result["state_changed"] is True
        assert survivor_result["fencing_version"] == pending_version
        assert survivor_result["resource_version"] == pending_version
        assert survivor_result["automatic_control_allowed"] is False
        assert survivor_result["activation_allowed"] is False
        assert survivor_result["traffic_switching_allowed"] is False

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


def test_heterogeneous_waiter_ordering_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "power-loss" in combined
    assert "production readiness" in combined
    assert "performance" in combined
    assert "novelty" in combined
