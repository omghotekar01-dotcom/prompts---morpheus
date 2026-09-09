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
from test_process_transfer_protected_resource_fencing_sqlite_long_waiter_loss_reconstruction import (
    SHORT_TIMEOUT_BUDGETS_SECONDS,
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


BASE_COUNTER = 2901
RECONSTRUCTION_CYCLES = 2


def _run_concurrent_heterogeneous_contenders(
    context: mp.context.BaseContext,
    database: Path,
    *,
    holder: mp.Process,
    pending_counter: int,
    pending_mutation_id: str,
    pending_value: str,
    label: str,
) -> list[dict[str, object]]:
    ready = context.Queue()
    release = context.Event()
    results = context.Queue()
    contenders: list[mp.Process] = []

    for contender_index, timeout_seconds in enumerate(
        SHORT_TIMEOUT_BUDGETS_SECONDS, start=1
    ):
        actor = f"{label}-heterogeneous-{contender_index}"
        contender = context.Process(
            target=_contend_for_pending_generation,
            args=(
                str(database),
                actor,
                timeout_seconds,
                ready,
                release,
                results,
                pending_counter,
                f"{pending_mutation_id}-{actor}",
                f"{pending_value}-{actor}",
            ),
            name=actor,
        )
        contender.start()
        contenders.append(contender)

    expected_actors = {child.name for child in contenders}
    assert {ready.get(timeout=10.0) for _ in contenders} == expected_actors
    assert holder.is_alive()

    # Release both reconstructed production writers together while the staged holder owns the
    # SQLite write transaction. The deliberately different timeout budgets are bounded test
    # inputs only; they do not establish latency, fairness, or scheduler guarantees.
    release.set()
    outcomes = [results.get(timeout=10.0) for _ in contenders]
    for contender in contenders:
        _join_cleanly(contender, contender.name)

    assert {str(result["actor"]) for result in outcomes} == expected_actors
    assert all(result["kind"] == "sqlite-failure" for result in outcomes)
    assert all(
        "SQLite transactionally fenced protected-resource mutation failed"
        in str(result["message"])
        for result in outcomes
    )
    assert holder.is_alive()
    return outcomes


def test_concurrent_heterogeneous_contention_during_repeated_reconstruction_preserves_generation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "concurrent-heterogeneous-reconstruction.sqlite3"
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
    pending_mutation_id = f"mutation-{pending_counter}-heterogeneous-reconstruction"
    pending_value = f"committed-{pending_counter}-heterogeneous-reconstruction"

    # E73 evidence gate: the existing E72 regression retains the complete preceding dependency
    # chain. This test adds simultaneous heterogeneous timeout contention during every repeated
    # fresh staged reconstruction of the same pending generation. Every holder is deliberately
    # terminated only at the known staged-but-uncommitted boundary after both contenders fail.
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
            name=f"heterogeneous-reconstruction-holder-{reconstruction_index}",
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

        outcomes = _run_concurrent_heterogeneous_contenders(
            context,
            database,
            holder=holder,
            pending_counter=pending_counter,
            pending_mutation_id=pending_mutation_id,
            pending_value=pending_value,
            label=f"reconstruction-{reconstruction_index}",
        )
        assert len(outcomes) == len(SHORT_TIMEOUT_BUDGETS_SECONDS)
        assert holder.is_alive()
        _assert_committed_pair(database, long_lived_reader, current_expected)
        _assert_committed_pair(database, fresh_reader, current_expected)

        _terminate_holder(holder)
        _assert_write_lock_released(database)
        _assert_committed_pair(database, long_lived_reader, current_expected)
        _assert_committed_pair(database, fresh_reader, current_expected)

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

    stale = recovery_writer.mutate(
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
    _assert_committed_pair(database, long_lived_reader, recovered_expected)

    replay = recovery_writer.mutate(
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
    successor = recovery_writer.mutate(
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


def test_concurrent_heterogeneous_reconstruction_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "power-loss" in combined
    assert "production readiness" in combined
    assert "performance" in combined
    assert "novelty" in combined
