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
from test_process_transfer_protected_resource_fencing_sqlite_mixed_contention_forced_loss import (
    AUTHORITY_ID,
    RESOURCE_ID,
    _assert_write_lock_released,
    _expected_pair,
    _pair_payload,
    _run_mixed_round,
    _stage_uncommitted_next_generation,
)


BASE_COUNTER = 901
ROUNDS = 2
LOSS_BURST = 3


def _kill_staged_next_generation(
    *,
    context: mp.context.BaseContext,
    database: Path,
    counter: int,
    version: int,
) -> None:
    ready = context.Queue()
    hold = context.Event()
    child = context.Process(
        target=_stage_uncommitted_next_generation,
        args=(str(database), ready, hold, counter, version),
    )
    child.start()
    assert ready.get(timeout=10.0) == {"counter": counter, "version": version}
    assert child.is_alive()
    child.terminate()
    child.join(timeout=10.0)
    if child.is_alive():
        raise AssertionError("forced-loss burst child remained alive")
    assert child.exitcode is not None and child.exitcode != 0


def test_repeated_forced_loss_bursts_preserve_pending_generation_until_contention_recovery(
    tmp_path: Path,
) -> None:
    database = tmp_path / "forced-loss-burst-recovery.sqlite3"
    writer = SQLiteTransactionallyFencedProtectedResource(database, timeout_seconds=3.0)
    long_lived_reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=3.0)
    context = mp.get_context("spawn")

    current_counter = BASE_COUNTER
    current_mutation_id = f"mutation-{BASE_COUNTER}"
    current_value = f"committed-{BASE_COUNTER}"
    base = writer.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        current_counter,
        mutation_id=current_mutation_id,
        value=current_value,
    )
    assert base.outcome == "applied"
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

        expected_version += 1
        current_counter, current_mutation_id, current_value, expected = _run_mixed_round(
            context=context,
            database=database,
            current_counter=current_counter,
            current_mutation_id=current_mutation_id,
            current_value=current_value,
            expected_version=expected_version,
        )
        assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected

        pending_counter = current_counter + 1
        pending_version = expected_version + 1
        for burst_index in range(LOSS_BURST):
            _kill_staged_next_generation(
                context=context,
                database=database,
                counter=pending_counter,
                version=pending_version,
            )

            # Every independently reconstructed/killed writer targeted the same pending
            # generation. None may leak a staged row or consume that generation.
            _assert_write_lock_released(database)
            assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
            reconstructed = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=3.0)
            assert _pair_payload(reconstructed.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected

            stale = writer.mutate(
                RESOURCE_ID,
                AUTHORITY_ID,
                previous_counter,
                mutation_id=previous_mutation_id,
                value=previous_value,
            )
            assert stale.outcome == "stale"
            assert stale.accepted is False
            assert stale.state_changed is False

            replay = writer.mutate(
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
            assert _pair_payload(reconstructed.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
            _assert_write_lock_released(database)

        # The next round must still be able to race for exactly the generation repeatedly
        # staged and lost above. On the final round, exercise that recovery immediately.
        if round_index == ROUNDS:
            expected_version += 1
            recovered_counter, recovered_mutation_id, recovered_value, recovered_expected = _run_mixed_round(
                context=context,
                database=database,
                current_counter=current_counter,
                current_mutation_id=current_mutation_id,
                current_value=current_value,
                expected_version=expected_version,
            )
            assert recovered_counter == pending_counter
            assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == recovered_expected
            assert _pair_payload(
                SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=3.0).snapshot_pair(
                    RESOURCE_ID, AUTHORITY_ID
                )
            ) == recovered_expected
            current_counter = recovered_counter
            current_mutation_id = recovered_mutation_id
            current_value = recovered_value
            expected = recovered_expected
            _assert_write_lock_released(database)

    successor = writer.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        current_counter + 1,
        mutation_id=f"mutation-{current_counter + 1}-successor",
        value=f"committed-{current_counter + 1}-successor",
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


def test_forced_loss_burst_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "power-loss" in combined
    assert "production readiness" in combined
    assert "benchmark" in combined
    assert "novelty" in combined
