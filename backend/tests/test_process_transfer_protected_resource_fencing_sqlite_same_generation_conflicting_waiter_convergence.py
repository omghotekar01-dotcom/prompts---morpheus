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
    _join_cleanly,
)
from test_process_transfer_protected_resource_fencing_sqlite_replacement_waiter_reconstruction_recovery import (
    _start_replacement_waiter,
)


BASE_COUNTER = 3301


def test_conflicting_same_generation_waiters_fail_closed_after_holder_loss(
    tmp_path: Path,
) -> None:
    database = tmp_path / "same-generation-conflicting-waiter-convergence.sqlite3"
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
    contender_payloads = {
        "alpha": (
            f"mutation-{pending_counter}-conflict-alpha",
            f"committed-{pending_counter}-conflict-alpha",
        ),
        "beta": (
            f"mutation-{pending_counter}-conflict-beta",
            f"committed-{pending_counter}-conflict-beta",
        ),
    }

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
        name="conflicting-waiter-holder",
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

    alpha, alpha_results = _start_replacement_waiter(
        context,
        database,
        pending_counter=pending_counter,
        pending_mutation_id=contender_payloads["alpha"][0],
        pending_value=contender_payloads["alpha"][1],
        label="conflicting-alpha",
    )
    beta, beta_results = _start_replacement_waiter(
        context,
        database,
        pending_counter=pending_counter,
        pending_mutation_id=contender_payloads["beta"][0],
        pending_value=contender_payloads["beta"][1],
        label="conflicting-beta",
    )

    # E77 evidence gate: two independently reconstructed production writers request the
    # same pending fencing generation with different mutation identities and values. While
    # the staged holder owns SQLite's write transaction, both must remain blocked and no
    # pending state may become reader-visible.
    assert alpha.is_alive()
    assert beta.is_alive()
    assert holder.is_alive()
    _assert_committed_pair(database, long_lived_reader, current_expected)
    _assert_committed_pair(database, fresh_reader, current_expected)

    # Controlled rollback releases both conflicting waiters. SQLite scheduling may choose
    # either winner; MORPHEUS must not depend on which one wins. Exactly one mutation may
    # advance the generation, and the other must fail closed as same-generation reuse.
    _terminate_holder(holder)
    alpha_outcome = alpha_results.get(timeout=10.0)
    beta_outcome = beta_results.get(timeout=10.0)
    _join_cleanly(alpha, "alpha conflicting same-generation waiter")
    _join_cleanly(beta, "beta conflicting same-generation waiter")

    outcomes = {"alpha": alpha_outcome, "beta": beta_outcome}
    assert all(outcome["kind"] == "outcome" for outcome in outcomes.values())
    assert [outcome["outcome"] for outcome in outcomes.values()].count("applied") == 1
    assert (
        [outcome["outcome"] for outcome in outcomes.values()].count(
            "generation_reuse_rejected"
        )
        == 1
    )

    winner_name = next(
        name for name, outcome in outcomes.items() if outcome["outcome"] == "applied"
    )
    loser_name = "beta" if winner_name == "alpha" else "alpha"
    winner = outcomes[winner_name]
    loser = outcomes[loser_name]

    assert winner["accepted"] is True
    assert winner["state_changed"] is True
    assert winner["fencing_version"] == pending_version
    assert winner["resource_version"] == pending_version

    assert loser["accepted"] is False
    assert loser["state_changed"] is False
    assert loser["fencing_version"] == pending_version
    assert loser["resource_version"] == pending_version

    for outcome in outcomes.values():
        assert outcome["automatic_control_allowed"] is False
        assert outcome["activation_allowed"] is False
        assert outcome["traffic_switching_allowed"] is False

    winning_mutation_id, winning_value = contender_payloads[winner_name]
    losing_mutation_id, losing_value = contender_payloads[loser_name]
    recovered_expected = _expected_pair(
        counter=pending_counter,
        version=pending_version,
        mutation_id=winning_mutation_id,
        value=winning_value,
    )
    _assert_committed_pair(database, long_lived_reader, recovered_expected)
    _assert_committed_pair(database, fresh_reader, recovered_expected)
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

    losing_replay = verification_writer.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        pending_counter,
        mutation_id=losing_mutation_id,
        value=losing_value,
    )
    assert losing_replay.outcome == "generation_reuse_rejected"
    assert losing_replay.accepted is False
    assert losing_replay.state_changed is False
    assert losing_replay.fencing_version == pending_version
    assert losing_replay.resource_version == pending_version

    winning_replay = verification_writer.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        pending_counter,
        mutation_id=winning_mutation_id,
        value=winning_value,
    )
    assert winning_replay.outcome == "idempotent"
    assert winning_replay.accepted is True
    assert winning_replay.state_changed is False
    assert winning_replay.fencing_version == pending_version
    assert winning_replay.resource_version == pending_version
    assert winning_replay.automatic_control_allowed is False
    assert winning_replay.activation_allowed is False
    assert winning_replay.traffic_switching_allowed is False

    _assert_committed_pair(database, long_lived_reader, recovered_expected)
    _assert_write_lock_released(database)

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


def test_conflicting_same_generation_waiter_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "power-loss" in combined
    assert "production readiness" in combined
    assert "performance" in combined
    assert "novelty" in combined
