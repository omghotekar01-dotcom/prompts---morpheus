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


BASE_COUNTER = 1101
ROUNDS = 2
CONTENDERS = 3
SHORT_TIMEOUT_SECONDS = 0.25


def _short_timeout_contender(
    database: str,
    contender_index: int,
    ready: mp.Queue,
    release: mp.Event,
    results: mp.Queue,
    pending_counter: int,
    mutation_id: str,
    value: str,
) -> None:
    """Reconstruct independently, then contend only after the parent releases the gate."""
    writer = SQLiteTransactionallyFencedProtectedResource(
        database,
        timeout_seconds=SHORT_TIMEOUT_SECONDS,
    )
    ready.put(contender_index)
    if not release.wait(timeout=10.0):
        results.put({"index": contender_index, "kind": "gate-timeout"})
        return

    try:
        outcome = writer.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            pending_counter,
            mutation_id=mutation_id,
            value=value,
        )
    except ValueError as exc:
        results.put(
            {
                "index": contender_index,
                "kind": "timeout",
                "message": str(exc),
            }
        )
        return

    results.put(
        {
            "index": contender_index,
            "kind": "unexpected-result",
            "outcome": outcome.outcome,
            "accepted": outcome.accepted,
            "state_changed": outcome.state_changed,
        }
    )


def _join_cleanly(children: list[mp.Process]) -> None:
    for child in children:
        child.join(timeout=10.0)
        if child.is_alive():
            child.terminate()
            child.join(timeout=10.0)
            raise AssertionError("short-timeout contender remained alive")
        assert child.exitcode == 0


def test_multiple_short_timeout_contenders_fail_closed_then_pending_generation_recovers(
    tmp_path: Path,
) -> None:
    database = tmp_path / "multi-contender-busy-timeout-recovery.sqlite3"
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
        pending_mutation_id = f"mutation-{pending_counter}-multi-timeout-recovery"
        pending_value = f"committed-{pending_counter}-multi-timeout-recovery"

        # Each contender reconstructs its own SQLite writer before the holder acquires the
        # write transaction. This isolates the exercised timeout to mutate()/BEGIN IMMEDIATE
        # rather than constructor/schema initialization.
        contender_ready = context.Queue()
        release_contenders = context.Event()
        contender_results = context.Queue()
        contenders = [
            context.Process(
                target=_short_timeout_contender,
                args=(
                    str(database),
                    contender_index,
                    contender_ready,
                    release_contenders,
                    contender_results,
                    pending_counter,
                    pending_mutation_id,
                    pending_value,
                ),
            )
            for contender_index in range(CONTENDERS)
        ]
        for contender in contenders:
            contender.start()
        assert {contender_ready.get(timeout=10.0) for _ in contenders} == set(
            range(CONTENDERS)
        )

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
        assert _pair_payload(
            SQLiteTransactionConsistentFencingResourceReader(
                database, timeout_seconds=3.0
            ).snapshot_pair(RESOURCE_ID, AUTHORITY_ID)
        ) == expected

        release_contenders.set()
        results = [contender_results.get(timeout=10.0) for _ in contenders]
        _join_cleanly(contenders)

        assert {result["index"] for result in results} == set(range(CONTENDERS))
        assert all(result["kind"] == "timeout" for result in results)
        assert all(
            "SQLite transactionally fenced protected-resource mutation failed"
            in result["message"]
            for result in results
        )

        # None of the independently reconstructed contenders may expose or consume the
        # holder's uncommitted generation. The holder remains alive until the parent ends it.
        assert holder.is_alive()
        assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
        assert _pair_payload(
            SQLiteTransactionConsistentFencingResourceReader(
                database, timeout_seconds=3.0
            ).snapshot_pair(RESOURCE_ID, AUTHORITY_ID)
        ) == expected

        _terminate_holder(holder)
        _assert_write_lock_released(database)

        # Reconstruct one normal-timeout writer and commit exactly the generation that every
        # short-timeout contender failed to acquire while it was held uncommitted.
        recovered_writer = SQLiteTransactionallyFencedProtectedResource(
            database, timeout_seconds=3.0
        )
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
            SQLiteTransactionConsistentFencingResourceReader(
                database, timeout_seconds=3.0
            ).snapshot_pair(RESOURCE_ID, AUTHORITY_ID)
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


def test_multi_contender_busy_timeout_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "power-loss" in combined
    assert "production readiness" in combined
    assert "performance" in combined
    assert "novelty" in combined
