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


RESOURCE_ID = "resource-repeated-next-generation"
AUTHORITY_ID = "authority-repeated-next-generation"
BASE_COUNTER = 501
ROUNDS = 3
CONTENDERS = 4


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


def _round_worker(
    database: str,
    counter: int,
    start: mp.Event,
    ready: mp.Queue,  # type: ignore[type-arg]
    output: mp.Queue,  # type: ignore[type-arg]
    mutation_id: str,
    value: str,
) -> None:
    try:
        writer = SQLiteTransactionallyFencedProtectedResource(database, timeout_seconds=3.0)
        reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=3.0)
        ready.put(True)
        if not start.wait(timeout=10.0):
            raise AssertionError("repeated contention start gate was not released")

        result = writer.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            counter,
            mutation_id=mutation_id,
            value=value,
        )
        observed = _pair_payload(reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID))
        output.put(
            {
                "ok": True,
                "counter": counter,
                "mutation_id": mutation_id,
                "requested_value": value,
                "outcome": result.outcome,
                "accepted": result.accepted,
                "state_changed": result.state_changed,
                "fencing_version": result.fencing_version,
                "resource_version": result.resource_version,
                "value": result.value,
                "automatic_control_allowed": result.automatic_control_allowed,
                "activation_allowed": result.activation_allowed,
                "traffic_switching_allowed": result.traffic_switching_allowed,
                "observed": observed,
            }
        )
    except Exception as exc:  # pragma: no cover - surfaced through parent assertion
        output.put({"ok": False, "counter": counter, "mutation_id": mutation_id, "error": repr(exc)})
        raise


def _assert_write_lock_released(database: Path) -> None:
    connection = sqlite3.connect(str(database), timeout=3.0, isolation_level=None)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.rollback()
    finally:
        connection.close()


def test_repeated_spawned_next_generation_contention_advances_monotonically(tmp_path: Path) -> None:
    database = tmp_path / "repeated-next-generation.sqlite3"
    writer = SQLiteTransactionallyFencedProtectedResource(database, timeout_seconds=3.0)
    long_lived_reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=3.0)

    base = writer.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        BASE_COUNTER,
        mutation_id="mutation-501",
        value="committed-501",
    )
    assert base.outcome == "applied"
    assert base.accepted is True
    assert base.state_changed is True

    expected = _expected_pair(
        counter=BASE_COUNTER,
        version=1,
        mutation_id="mutation-501",
        value="committed-501",
    )
    assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected

    previous_counter = BASE_COUNTER
    previous_mutation_id = "mutation-501"
    previous_value = "committed-501"
    context = mp.get_context("spawn")

    for round_index in range(1, ROUNDS + 1):
        counter = BASE_COUNTER + round_index
        expected_version = round_index + 1
        start = context.Event()
        ready = context.Queue()
        output = context.Queue()
        requests = [
            (f"mutation-{counter}-{suffix}", f"candidate-{counter}-{suffix}")
            for suffix in ("a", "b", "c", "d")
        ]
        children = [
            context.Process(
                target=_round_worker,
                args=(str(database), counter, start, ready, output, mutation_id, value),
            )
            for mutation_id, value in requests
        ]

        for child in children:
            child.start()
        for _ in children:
            assert ready.get(timeout=10.0) is True
        start.set()

        for child in children:
            child.join(timeout=20.0)
            if child.is_alive():
                child.terminate()
                child.join(timeout=2.0)
                raise AssertionError(f"contention child did not finish in round {round_index}")
            assert child.exitcode == 0

        payloads = [output.get(timeout=2.0) for _ in children]
        assert all(payload["ok"] is True for payload in payloads), payloads

        applied = [payload for payload in payloads if payload["outcome"] == "applied"]
        rejected = [payload for payload in payloads if payload["outcome"] == "generation_reuse_rejected"]
        assert len(applied) == 1
        assert len(rejected) == CONTENDERS - 1

        winner = applied[0]
        assert winner["accepted"] is True
        assert winner["state_changed"] is True
        assert winner["fencing_version"] == expected_version
        assert winner["resource_version"] == expected_version
        assert winner["value"] == winner["requested_value"]

        expected = _expected_pair(
            counter=counter,
            version=expected_version,
            mutation_id=str(winner["mutation_id"]),
            value=str(winner["requested_value"]),
        )
        for payload in rejected:
            assert payload["accepted"] is False
            assert payload["state_changed"] is False
            assert payload["fencing_version"] == expected_version
            assert payload["resource_version"] == expected_version
            assert payload["value"] == winner["requested_value"]

        for payload in payloads:
            assert payload["automatic_control_allowed"] is False
            assert payload["activation_allowed"] is False
            assert payload["traffic_switching_allowed"] is False
            assert payload["observed"] == expected

        assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
        fresh_reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=3.0)
        assert _pair_payload(fresh_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected

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
        assert stale.fencing_version == expected_version
        assert stale.resource_version == expected_version
        assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected

        replay = writer.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            counter,
            mutation_id=str(winner["mutation_id"]),
            value=str(winner["requested_value"]),
        )
        assert replay.outcome == "idempotent"
        assert replay.accepted is True
        assert replay.state_changed is False
        assert replay.fencing_version == expected_version
        assert replay.resource_version == expected_version
        assert _pair_payload(fresh_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected

        _assert_write_lock_released(database)
        previous_counter = counter
        previous_mutation_id = str(winner["mutation_id"])
        previous_value = str(winner["requested_value"])

    successor_counter = BASE_COUNTER + ROUNDS + 1
    successor_version = ROUNDS + 2
    successor = writer.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        successor_counter,
        mutation_id=f"mutation-{successor_counter}",
        value=f"committed-{successor_counter}",
    )
    assert successor.outcome == "applied"
    assert successor.accepted is True
    assert successor.state_changed is True
    assert successor.fencing_version == successor_version
    assert successor.resource_version == successor_version
    assert successor.automatic_control_allowed is False
    assert successor.activation_allowed is False
    assert successor.traffic_switching_allowed is False

    expected_successor = _expected_pair(
        counter=successor_counter,
        version=successor_version,
        mutation_id=f"mutation-{successor_counter}",
        value=f"committed-{successor_counter}",
    )
    assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected_successor
    final_reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=3.0)
    assert _pair_payload(final_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected_successor
    _assert_write_lock_released(database)


def test_repeated_next_generation_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "production readiness" in combined
    assert "benchmark" in combined
    assert "novelty" in combined
