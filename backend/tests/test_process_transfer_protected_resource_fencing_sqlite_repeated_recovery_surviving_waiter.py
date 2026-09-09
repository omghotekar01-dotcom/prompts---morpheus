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
from test_process_transfer_protected_resource_fencing_sqlite_long_waiter_loss_reconstruction import (
    LONG_WAITER_TIMEOUT_SECONDS,
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
from test_process_transfer_protected_resource_fencing_sqlite_replacement_long_waiter_loss_reconstruction import (
    _start_blocked_waiter,
)


BASE_COUNTER = 2601
RECOVERY_CYCLES = 3


def _assert_short_timeouts_fail_closed(
    database: Path,
    *,
    pending_counter: int,
    pending_mutation_id: str,
    pending_value: str,
    holder: mp.Process,
    long_lived_reader: SQLiteTransactionConsistentFencingResourceReader,
    current_expected: dict[str, object],
    label: str,
) -> None:
    for contender_index, timeout_seconds in enumerate(
        SHORT_TIMEOUT_BUDGETS_SECONDS, start=1
    ):
        contender = SQLiteTransactionallyFencedProtectedResource(
            database, timeout_seconds=timeout_seconds
        )
        with pytest.raises(
            ValueError,
            match="SQLite transactionally fenced protected-resource mutation failed",
        ):
            contender.mutate(
                RESOURCE_ID,
                AUTHORITY_ID,
                pending_counter,
                mutation_id=f"{pending_mutation_id}-{label}-short-{contender_index}",
                value=f"{pending_value}-{label}-short-{contender_index}",
            )
        assert holder.is_alive()
        _assert_committed_pair(database, long_lived_reader, current_expected)


def _start_surviving_waiter(
    context: mp.context.BaseContext,
    database: Path,
    *,
    pending_counter: int,
    pending_mutation_id: str,
    pending_value: str,
) -> tuple[mp.Process, mp.Queue]:
    ready = context.Queue()
    release = context.Event()
    results = context.Queue()
    waiter = context.Process(
        target=_contend_for_pending_generation,
        args=(
            str(database),
            "surviving-final-recovery-waiter",
            LONG_WAITER_TIMEOUT_SECONDS,
            ready,
            release,
            results,
            pending_counter,
            pending_mutation_id,
            pending_value,
        ),
        name="surviving-final-recovery-waiter",
    )
    waiter.start()
    assert ready.get(timeout=10.0) == "surviving-final-recovery-waiter"
    release.set()
    assert waiter.is_alive()
    return waiter, results


def test_repeated_recovery_timeout_contention_allows_final_surviving_waiter(
    tmp_path: Path,
) -> None:
    database = tmp_path / "repeated-recovery-surviving-waiter.sqlite3"
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
    pending_mutation_id = f"mutation-{pending_counter}-surviving-waiter"
    pending_value = f"committed-{pending_counter}-surviving-waiter"

    # Preserve E68's dependency chain before the repeated recovery cycles: short contenders fail
    # closed, then both an original and replacement longer-timeout non-owner are lost while the
    # original staged holder remains alive. Timeout values are bounded deterministic test inputs;
    # they do not establish fairness, scheduling, or latency guarantees.
    holder_ready = context.Queue()
    holder_hold = context.Event()
    holder = context.Process(
        target=_stage_uncommitted_next_generation,
        args=(
            str(database),
            holder_ready,
            holder_hold,
            pending_counter,
            pending_version,
        ),
        name="surviving-waiter-original-holder",
    )
    holder.start()
    assert holder_ready.get(timeout=10.0) == {
        "counter": pending_counter,
        "version": pending_version,
    }
    assert holder.is_alive()
    _assert_committed_pair(database, long_lived_reader, current_expected)

    _assert_short_timeouts_fail_closed(
        database,
        pending_counter=pending_counter,
        pending_mutation_id=pending_mutation_id,
        pending_value=pending_value,
        holder=holder,
        long_lived_reader=long_lived_reader,
        current_expected=current_expected,
        label="original-holder",
    )

    original_waiter = _start_blocked_waiter(
        context,
        database,
        name="original-long-waiter-before-surviving-recovery",
        pending_counter=pending_counter,
        pending_mutation_id=pending_mutation_id,
        pending_value=pending_value,
    )
    _terminate_holder(original_waiter)
    assert holder.is_alive()
    _assert_committed_pair(database, long_lived_reader, current_expected)

    replacement_waiter = _start_blocked_waiter(
        context,
        database,
        name="replacement-long-waiter-before-surviving-recovery",
        pending_counter=pending_counter,
        pending_mutation_id=pending_mutation_id,
        pending_value=pending_value,
    )
    _terminate_holder(replacement_waiter)
    assert holder.is_alive()
    _assert_committed_pair(database, long_lived_reader, current_expected)

    _terminate_holder(holder)
    _assert_write_lock_released(database)
    _assert_committed_pair(database, long_lived_reader, current_expected)

    surviving_waiter: mp.Process | None = None
    surviving_results: mp.Queue | None = None

    # Reconstruct the exact same pending generation repeatedly. Earlier staged recovery writers
    # are deliberately lost before commit. On the final cycle, one longer-timeout production
    # writer survives the holder loss and must serialize the unchanged pending generation once.
    for recovery_index in range(1, RECOVERY_CYCLES + 1):
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
            name=f"surviving-waiter-recovery-holder-{recovery_index}",
        )
        recovery.start()
        assert recovery_ready.get(timeout=10.0) == {
            "counter": pending_counter,
            "version": pending_version,
        }
        assert recovery.is_alive()
        _assert_committed_pair(database, long_lived_reader, current_expected)

        fresh_reader = SQLiteTransactionConsistentFencingResourceReader(
            database, timeout_seconds=3.0
        )
        _assert_committed_pair(database, fresh_reader, current_expected)

        _assert_short_timeouts_fail_closed(
            database,
            pending_counter=pending_counter,
            pending_mutation_id=pending_mutation_id,
            pending_value=pending_value,
            holder=recovery,
            long_lived_reader=long_lived_reader,
            current_expected=current_expected,
            label=f"recovery-{recovery_index}",
        )
        _assert_committed_pair(database, fresh_reader, current_expected)

        if recovery_index == RECOVERY_CYCLES:
            surviving_waiter, surviving_results = _start_surviving_waiter(
                context,
                database,
                pending_counter=pending_counter,
                pending_mutation_id=pending_mutation_id,
                pending_value=pending_value,
            )
            assert recovery.is_alive()
            assert surviving_waiter.is_alive()
            _assert_committed_pair(database, long_lived_reader, current_expected)
            _assert_committed_pair(database, fresh_reader, current_expected)

        # Fault injection remains restricted to the known staged-but-uncommitted boundary. This
        # is bounded SQLite rollback evidence, not arbitrary process-kill or durability evidence.
        _terminate_holder(recovery)

        if recovery_index < RECOVERY_CYCLES:
            _assert_write_lock_released(database)
            _assert_committed_pair(database, long_lived_reader, current_expected)
            _assert_committed_pair(database, fresh_reader, current_expected)

    assert surviving_waiter is not None
    assert surviving_results is not None
    _join_cleanly(surviving_waiter, "surviving final recovery waiter")
    waiter_result = surviving_results.get(timeout=10.0)
    assert waiter_result == {
        "actor": "surviving-final-recovery-waiter",
        "kind": "outcome",
        "outcome": "applied",
        "accepted": True,
        "state_changed": True,
        "fencing_version": pending_version,
        "resource_version": pending_version,
        "automatic_control_allowed": False,
        "activation_allowed": False,
        "traffic_switching_allowed": False,
    }

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

    verifier = SQLiteTransactionallyFencedProtectedResource(database, timeout_seconds=3.0)
    stale = verifier.mutate(
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

    replay = verifier.mutate(
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
    _assert_committed_pair(database, long_lived_reader, recovered_expected)

    successor_counter = pending_counter + 1
    successor = verifier.mutate(
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


def test_repeated_recovery_surviving_waiter_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "power-loss" in combined
    assert "production readiness" in combined
    assert "performance" in combined
    assert "novelty" in combined
