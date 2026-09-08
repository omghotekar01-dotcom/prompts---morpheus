from __future__ import annotations

import multiprocessing as mp
from pathlib import Path
import sqlite3

from app.process_transfer_protected_resource_fencing_sqlite_resource import (
    SQLiteTransactionallyFencedProtectedResource,
    TRUTH_BOUNDARY as RESOURCE_TRUTH_BOUNDARY,
)
from app.process_transfer_protected_resource_fencing_sqlite_snapshot import (
    SQLiteTransactionConsistentFencingResourceReader,
    TRUTH_BOUNDARY as READER_TRUTH_BOUNDARY,
)
from test_process_transfer_protected_resource_fencing_sqlite_repeated_mixed_generation_contention import (
    _mixed_round_worker,
)


RESOURCE_ID = "resource-repeated-mixed-generation"
AUTHORITY_ID = "authority-repeated-mixed-generation"
BASE_COUNTER = 801
ROUNDS = 3
NEXT_CONTENDERS = 4


def _pair_payload(pair) -> dict[str, object]:  # type: ignore[no-untyped-def]
    assert pair is not None
    return {
        "fencing_counter": pair.fencing.fencing_counter,
        "fencing_version": pair.fencing.version,
        "resource_version": pair.resource.resource_version,
        "value": pair.resource.value,
        "last_mutation_id": pair.resource.last_mutation_id,
        "last_fencing_counter": pair.resource.last_fencing_counter,
        "automatic_control_allowed": pair.automatic_control_allowed,
        "activation_allowed": pair.activation_allowed,
        "traffic_switching_allowed": pair.traffic_switching_allowed,
    }


def _expected_pair(*, counter: int, version: int, mutation_id: str, value: str) -> dict[str, object]:
    return {
        "fencing_counter": counter,
        "fencing_version": version,
        "resource_version": version,
        "value": value,
        "last_mutation_id": mutation_id,
        "last_fencing_counter": counter,
        "automatic_control_allowed": False,
        "activation_allowed": False,
        "traffic_switching_allowed": False,
    }


def _stage_uncommitted_next_generation(
    database: str,
    ready: mp.Queue,  # type: ignore[type-arg]
    hold: mp.Event,
    counter: int,
    version: int,
) -> None:
    connection = sqlite3.connect(database, timeout=3.0, isolation_level=None)
    try:
        connection.execute("PRAGMA busy_timeout = 3000")
        connection.execute("BEGIN IMMEDIATE")
        fencing = connection.execute(
            "UPDATE morpheus_fencing_state SET fencing_counter = ?, version = ? "
            "WHERE resource_id = ? AND fencing_authority_id = ? AND version = ?",
            (counter, version, RESOURCE_ID, AUTHORITY_ID, version - 1),
        )
        resource = connection.execute(
            "UPDATE morpheus_protected_resource_state SET resource_version = ?, value = ?, "
            "last_mutation_id = ?, last_fencing_counter = ? "
            "WHERE resource_id = ? AND fencing_authority_id = ? AND resource_version = ?",
            (
                version,
                f"uncommitted-{counter}",
                f"uncommitted-mutation-{counter}",
                counter,
                RESOURCE_ID,
                AUTHORITY_ID,
                version - 1,
            ),
        )
        if fencing.rowcount != 1 or resource.rowcount != 1:
            raise AssertionError("forced-loss child did not stage exactly one coherent next-generation pair")
        ready.put({"counter": counter, "version": version})
        if hold.wait(timeout=30.0):
            raise AssertionError("forced-loss hold gate must not be released")
    finally:
        # The evidence path terminates the process before this executes. This rollback is
        # defensive only if the worker unexpectedly reaches normal teardown.
        connection.rollback()
        connection.close()


def _assert_write_lock_released(database: Path) -> None:
    connection = sqlite3.connect(str(database), timeout=3.0, isolation_level=None)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.rollback()
    finally:
        connection.close()


def _run_mixed_round(
    *,
    context: mp.context.BaseContext,
    database: Path,
    current_counter: int,
    current_mutation_id: str,
    current_value: str,
    expected_version: int,
) -> tuple[int, str, str, dict[str, object]]:
    next_counter = current_counter + 1
    start = context.Event()
    observe = context.Event()
    ready = context.Queue()
    mutations = context.Queue()
    observations = context.Queue()
    requests = [
        ("stale", current_counter - 1, f"retained-{current_counter - 1}", f"retained-{current_counter - 1}"),
        ("current-replay", current_counter, current_mutation_id, current_value),
        ("current-conflict", current_counter, f"{current_mutation_id}-conflict", f"conflict-{current_counter}"),
        *[
            (
                f"next-{suffix}",
                next_counter,
                f"mutation-{next_counter}-{suffix}",
                f"candidate-{next_counter}-{suffix}",
            )
            for suffix in ("a", "b", "c", "d")
        ],
    ]
    children = [
        context.Process(
            target=_mixed_round_worker,
            args=(
                str(database),
                start,
                observe,
                ready,
                mutations,
                observations,
                label,
                counter,
                mutation_id,
                value,
            ),
        )
        for label, counter, mutation_id, value in requests
    ]

    for child in children:
        child.start()
    assert {ready.get(timeout=10.0) for _ in children} == {request[0] for request in requests}
    start.set()

    payloads = [mutations.get(timeout=15.0) for _ in children]
    assert all(payload["ok"] is True for payload in payloads), payloads
    by_label = {str(payload["label"]): payload for payload in payloads}

    stale = by_label["stale"]
    assert stale["outcome"] == "stale"
    assert stale["accepted"] is False
    assert stale["state_changed"] is False

    replay = by_label["current-replay"]
    assert replay["outcome"] in {"idempotent", "stale"}
    assert replay["state_changed"] is False
    assert replay["accepted"] is (replay["outcome"] == "idempotent")

    conflict = by_label["current-conflict"]
    assert conflict["outcome"] in {"generation_reuse_rejected", "stale"}
    assert conflict["accepted"] is False
    assert conflict["state_changed"] is False

    contenders = [by_label[f"next-{suffix}"] for suffix in ("a", "b", "c", "d")]
    winners = [payload for payload in contenders if payload["outcome"] == "applied"]
    losers = [payload for payload in contenders if payload["outcome"] == "generation_reuse_rejected"]
    assert len(winners) == 1
    assert len(losers) == NEXT_CONTENDERS - 1
    winner = winners[0]
    assert winner["accepted"] is True
    assert winner["state_changed"] is True
    assert winner["fencing_version"] == expected_version
    assert winner["resource_version"] == expected_version
    for loser in losers:
        assert loser["accepted"] is False
        assert loser["state_changed"] is False
        assert loser["fencing_version"] == expected_version
        assert loser["resource_version"] == expected_version
        assert loser["value"] == winner["requested_value"]
    for payload in payloads:
        assert payload["automatic_control_allowed"] is False
        assert payload["activation_allowed"] is False
        assert payload["traffic_switching_allowed"] is False

    expected = _expected_pair(
        counter=next_counter,
        version=expected_version,
        mutation_id=str(winner["mutation_id"]),
        value=str(winner["requested_value"]),
    )
    observe.set()
    for child in children:
        child.join(timeout=20.0)
        if child.is_alive():
            child.terminate()
            child.join(timeout=2.0)
            raise AssertionError("mixed-contention child did not finish")
        assert child.exitcode == 0
    observed = [observations.get(timeout=2.0) for _ in children]
    assert all(payload["ok"] is True and payload["observed"] == expected for payload in observed)
    return next_counter, str(winner["mutation_id"]), str(winner["requested_value"]), expected


def test_repeated_mixed_contention_contains_forced_uncommitted_write_loss(tmp_path: Path) -> None:
    database = tmp_path / "mixed-contention-forced-loss.sqlite3"
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
    expected = _expected_pair(
        counter=current_counter,
        version=1,
        mutation_id=current_mutation_id,
        value=current_value,
    )
    assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected

    for round_index in range(1, ROUNDS + 1):
        expected_version = round_index + 1
        previous_counter = current_counter
        previous_mutation_id = current_mutation_id
        previous_value = current_value
        current_counter, current_mutation_id, current_value, expected = _run_mixed_round(
            context=context,
            database=database,
            current_counter=current_counter,
            current_mutation_id=current_mutation_id,
            current_value=current_value,
            expected_version=expected_version,
        )
        assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
        assert _pair_payload(
            SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=3.0).snapshot_pair(
                RESOURCE_ID, AUTHORITY_ID
            )
        ) == expected
        _assert_write_lock_released(database)

        ready = context.Queue()
        hold = context.Event()
        forced = context.Process(
            target=_stage_uncommitted_next_generation,
            args=(str(database), ready, hold, current_counter + 1, expected_version + 1),
        )
        forced.start()
        staged = ready.get(timeout=10.0)
        assert staged == {"counter": current_counter + 1, "version": expected_version + 1}

        # BEGIN IMMEDIATE plus the staged UPDATEs remain uncommitted. Concurrent readers
        # must continue seeing the last committed contention winner, never the staged pair.
        assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
        assert forced.is_alive()
        forced.terminate()
        forced.join(timeout=10.0)
        if forced.is_alive():
            raise AssertionError(f"forced-loss child remained alive in round {round_index}")
        assert forced.exitcode is not None and forced.exitcode != 0

        _assert_write_lock_released(database)
        assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
        reconstructed = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=3.0)
        assert _pair_payload(reconstructed.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected

        superseded = writer.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            previous_counter,
            mutation_id=previous_mutation_id,
            value=previous_value,
        )
        assert superseded.outcome == "stale"
        assert superseded.accepted is False
        assert superseded.state_changed is False

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

    successor_counter = current_counter + 1
    successor_version = ROUNDS + 2
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
    assert successor.fencing_version == successor_version
    assert successor.resource_version == successor_version
    assert successor.automatic_control_allowed is False
    assert successor.activation_allowed is False
    assert successor.traffic_switching_allowed is False

    final_pair = _expected_pair(
        counter=successor_counter,
        version=successor_version,
        mutation_id=f"mutation-{successor_counter}-successor",
        value=f"committed-{successor_counter}-successor",
    )
    assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == final_pair
    assert _pair_payload(
        SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=3.0).snapshot_pair(
            RESOURCE_ID, AUTHORITY_ID
        )
    ) == final_pair
    _assert_write_lock_released(database)


def test_forced_loss_composition_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "power-loss" in combined
    assert "production readiness" in combined
    assert "benchmark" in combined
    assert "novelty" in combined
