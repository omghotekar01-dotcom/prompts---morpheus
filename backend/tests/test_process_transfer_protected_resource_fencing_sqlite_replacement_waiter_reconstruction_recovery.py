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
from test_process_transfer_protected_resource_fencing_sqlite_asymmetric_reconstruction_contender_loss import (
    RECONSTRUCTION_CYCLES,
    _run_asymmetric_contender_fates,
)
from test_process_transfer_protected_resource_fencing_sqlite_busy_timeout_recovery import (
    _terminate_holder,
)
from test_process_transfer_protected_resource_fencing_sqlite_long_waiter_loss_reconstruction import (
    LONG_WAITER_TIMEOUT_SECONDS,
    _assert_committed_pair,
)
from test_process_transfer_protected_resource_fencing_sqlite_mixed_contention_forced_loss import (
    AUTHORITY_ID,
    RESOURCE_ID,
    _assert_write_lock_released,
    _expected_pair,
    _stage_uncommitted_next_generation,
)
from test_process_transfer_protected_resource_fencing_sqlite_mixed_timeout_waiter_recovery import (
    _contend_for_pending_generation,
    _join_cleanly,
)


BASE_COUNTER = 3101


def _start_replacement_waiter(
    context: mp.context.BaseContext,
    database: Path,
    *,
    pending_counter: int,
    pending_mutation_id: str,
    pending_value: str,
    label: str,
) -> tuple[mp.Process, mp.Queue]:
    ready = context.Queue()
    release = context.Event()
    results = context.Queue()
    actor = f"{label}-replacement-long-waiter"
    waiter = context.Process(
        target=_contend_for_pending_generation,
        args=(
            str(database),
            actor,
            LONG_WAITER_TIMEOUT_SECONDS,
            ready,
            release,
            results,
            pending_counter,
            pending_mutation_id,
            pending_value,
        ),
        name=actor,
    )
    waiter.start()
    assert ready.get(timeout=10.0) == actor
    release.set()
    assert waiter.is_alive()
    return waiter, results


def test_replacement_waiter_reconstruction_survives_final_holder_loss(
    tmp_path: Path,
) -> None:
    database = tmp_path / "replacement-waiter-reconstruction-recovery.sqlite3"
    writer = SQLiteTransactionallyFencedProtectedResource(database, timeout_seconds=3.0)
    long_lived_reader = SQLiteTransactionConsistentFencingResourceReader(
        database, timeout_seconds=3.0
    )
    context = mp.get_context("spawn")

    current_counter = BASE_COUNTER
    current_version = 1
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
    assert initial.fencing_version == current_version
    assert initial.resource_version == current_version
    assert initial.automatic_control_allowed is False
    assert initial.activation_allowed is False
    assert initial.traffic_switching_allowed is False

    current_expected = _expected_pair(
        counter=current_counter,
        version=current_version,
        mutation_id=current_mutation_id,
        value=current_value,
    )
    _assert_committed_pair(database, long_lived_reader, current_expected)

    pending_counter = current_counter + 1
    pending_version = current_version + 1
    pending_mutation_id = f"mutation-{pending_counter}-replacement-reconstruction"
    pending_value = f"committed-{pending_counter}-replacement-reconstruction"
    recovered = None

    # E75 evidence gate: after the E74 asymmetric contender outcomes, reconstruct a fresh
    # longer-timeout production waiter against the same still-live staged holder. Lose that
    # replacement too on a non-final cycle; on the final cycle, preserve it across deliberate
    # staged-holder loss and require it to commit the exact unchanged pending generation.
    for reconstruction_index in range(1, RECONSTRUCTION_CYCLES + 1):
        ready = context.Queue()
        hold = context.Event()
        holder = context.Process(
            target=_stage_uncommitted_next_generation,
            args=(
                str(database),
                ready,
                hold,
                pending_counter,
                pending_version,
            ),
            name=f"replacement-reconstruction-holder-{reconstruction_index}",
        )
        holder.start()
        assert ready.get(timeout=10.0) == {
            "counter": pending_counter,
            "version": pending_version,
        }
        assert holder.is_alive()

        fresh_reader = SQLiteTransactionConsistentFencingResourceReader(
            database, timeout_seconds=3.0
        )
        _assert_committed_pair(database, long_lived_reader, current_expected)
        _assert_committed_pair(database, fresh_reader, current_expected)

        short_outcome = _run_asymmetric_contender_fates(
            context,
            database,
            holder=holder,
            pending_counter=pending_counter,
            pending_mutation_id=pending_mutation_id,
            pending_value=pending_value,
            label=f"replacement-reconstruction-{reconstruction_index}",
        )
        assert short_outcome["kind"] == "sqlite-failure"
        assert holder.is_alive()

        replacement, replacement_results = _start_replacement_waiter(
            context,
            database,
            pending_counter=pending_counter,
            pending_mutation_id=pending_mutation_id,
            pending_value=pending_value,
            label=f"replacement-reconstruction-{reconstruction_index}",
        )
        assert holder.is_alive()
        assert replacement.is_alive()
        _assert_committed_pair(database, long_lived_reader, current_expected)
        _assert_committed_pair(database, fresh_reader, current_expected)

        if reconstruction_index < RECONSTRUCTION_CYCLES:
            _terminate_holder(replacement)
            assert holder.is_alive()
            _assert_committed_pair(database, long_lived_reader, current_expected)
            _assert_committed_pair(database, fresh_reader, current_expected)
            _terminate_holder(holder)
            _assert_write_lock_released(database)
            _assert_committed_pair(database, long_lived_reader, current_expected)
            _assert_committed_pair(database, fresh_reader, current_expected)
            continue

        # Final cycle: only the staged holder is lost. The already-blocked replacement waiter
        # must acquire the recovered SQLite write path and commit the exact same pending
        # generation. This is controlled local-process evidence, not a fairness/liveness claim.
        _terminate_holder(holder)
        replacement_outcome = replacement_results.get(timeout=10.0)
        _join_cleanly(replacement, "final replacement long waiter")
        assert replacement_outcome["kind"] == "outcome"
        assert replacement_outcome["outcome"] == "applied"
        assert replacement_outcome["accepted"] is True
        assert replacement_outcome["state_changed"] is True
        assert replacement_outcome["fencing_version"] == pending_version
        assert replacement_outcome["resource_version"] == pending_version
        assert replacement_outcome["automatic_control_allowed"] is False
        assert replacement_outcome["activation_allowed"] is False
        assert replacement_outcome["traffic_switching_allowed"] is False
        recovered = replacement_outcome

    assert recovered is not None
    recovered_expected = _expected_pair(
        counter=pending_counter,
        version=pending_version,
        mutation_id=pending_mutation_id,
        value=pending_value,
    )
    _assert_committed_pair(database, long_lived_reader, recovered_expected)
    fresh_after_recovery = SQLiteTransactionConsistentFencingResourceReader(
        database, timeout_seconds=3.0
    )
    _assert_committed_pair(database, fresh_after_recovery, recovered_expected)
    _assert_write_lock_released(database)

    verification_writer = SQLiteTransactionallyFencedProtectedResource(
        database, timeout_seconds=3.0
    )
    stale = verification_writer.mutate(
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

    replay = verification_writer.mutate(
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

    successor_counter = pending_counter + 1
    successor = verification_writer.mutate(
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


def test_replacement_waiter_reconstruction_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "power-loss" in combined
    assert "production readiness" in combined
    assert "performance" in combined
    assert "novelty" in combined
