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
from test_process_transfer_protected_resource_fencing_sqlite_replacement_waiter_forced_loss_recovery import (
    _fresh_pair,
)


BASE_COUNTER = 1901
RECOVERY_LOSSES = 3
CONTENDERS_PER_LOSS = 2
SHORT_TIMEOUT_SECONDS = 0.25


def test_repeated_recovery_writer_loss_with_timeout_contention_preserves_pending_generation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "repeated-recovery-loss-timeout-contention.sqlite3"
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
    assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
    assert _fresh_pair(database) == expected

    pending_counter = current_counter + 1
    pending_version = expected_version + 1
    pending_mutation_id = f"mutation-{pending_counter}-recovery-loss-timeout-contention"
    pending_value = f"committed-{pending_counter}-recovery-loss-timeout-contention"

    # Repeat a deterministic staged-but-uncommitted recovery loss while independently
    # reconstructed production writers contend through their bounded SQLite busy timeout.
    # This exercises one known fault boundary only; it is not evidence of arbitrary
    # instruction-boundary process-kill safety or a general scheduler/fairness property.
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
            name=f"recovery-timeout-contention-loss-{loss_index}",
        )
        recovery.start()
        assert recovery_ready.get(timeout=10.0) == {
            "counter": pending_counter,
            "version": pending_version,
        }
        assert recovery.is_alive()

        assert _pair_payload(
            long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)
        ) == expected
        assert _fresh_pair(database) == expected

        for contender_index in range(1, CONTENDERS_PER_LOSS + 1):
            contender = SQLiteTransactionallyFencedProtectedResource(
                database,
                timeout_seconds=SHORT_TIMEOUT_SECONDS,
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
                        f"{pending_mutation_id}-loss-{loss_index}-contender-{contender_index}"
                    ),
                    value=f"{pending_value}-contender-{contender_index}",
                )

            # Every timeout must fail closed while the recovery actor still owns the
            # uncommitted transaction. Neither the counter nor either row may advance.
            assert recovery.is_alive()
            assert _pair_payload(
                long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)
            ) == expected
            assert _fresh_pair(database) == expected

        _terminate_holder(recovery)
        _assert_write_lock_released(database)

        # Process loss rolls the staged transaction back. The exact same pending
        # generation must remain available after every repeated loss/contention cycle.
        assert _pair_payload(
            long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)
        ) == expected
        assert _fresh_pair(database) == expected

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

    recovered_expected = _expected_pair(
        counter=pending_counter,
        version=pending_version,
        mutation_id=pending_mutation_id,
        value=pending_value,
    )
    assert _pair_payload(
        long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)
    ) == recovered_expected
    assert _fresh_pair(database) == recovered_expected
    _assert_write_lock_released(database)

    stale = recovered_writer.mutate(
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

    replay = recovered_writer.mutate(
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
    assert _pair_payload(
        long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)
    ) == recovered_expected
    assert _fresh_pair(database) == recovered_expected
    _assert_write_lock_released(database)

    successor_counter = pending_counter + 1
    successor = recovered_writer.mutate(
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


def test_repeated_recovery_writer_loss_timeout_contention_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "power-loss" in combined
    assert "production readiness" in combined
    assert "performance" in combined
    assert "novelty" in combined
