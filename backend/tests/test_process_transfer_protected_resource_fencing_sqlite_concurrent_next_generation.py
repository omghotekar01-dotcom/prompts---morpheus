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


RESOURCE_ID = "resource-concurrent-next-generation"
AUTHORITY_ID = "authority-concurrent-next-generation"
BASE_COUNTER = 401
NEXT_COUNTER = BASE_COUNTER + 1


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


def _next_generation_worker(
    database: str,
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
            raise AssertionError("next-generation contention start gate was not released")

        result = writer.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            NEXT_COUNTER,
            mutation_id=mutation_id,
            value=value,
        )
        observed = _pair_payload(reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID))
        output.put(
            {
                "ok": True,
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
        output.put({"ok": False, "mutation_id": mutation_id, "error": repr(exc)})
        raise


def test_concurrent_spawned_next_generation_has_one_committed_winner(tmp_path: Path) -> None:
    database = tmp_path / "concurrent-next-generation.sqlite3"
    writer = SQLiteTransactionallyFencedProtectedResource(database, timeout_seconds=3.0)
    reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=3.0)

    base = writer.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        BASE_COUNTER,
        mutation_id="mutation-401",
        value="committed-401",
    )
    assert base.outcome == "applied"
    assert base.accepted is True
    assert base.state_changed is True

    expected_base = _expected_pair(
        counter=BASE_COUNTER,
        version=1,
        mutation_id="mutation-401",
        value="committed-401",
    )
    assert _pair_payload(reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected_base

    context = mp.get_context("spawn")
    start = context.Event()
    ready = context.Queue()
    output = context.Queue()
    requests = [
        ("mutation-402-a", "candidate-a"),
        ("mutation-402-b", "candidate-b"),
        ("mutation-402-c", "candidate-c"),
        ("mutation-402-d", "candidate-d"),
    ]
    children = [
        context.Process(
            target=_next_generation_worker,
            args=(str(database), start, ready, output, mutation_id, value),
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
            raise AssertionError("next-generation contention child did not finish")
        assert child.exitcode == 0

    payloads = [output.get(timeout=2.0) for _ in children]
    assert all(payload["ok"] is True for payload in payloads), payloads

    applied = [payload for payload in payloads if payload["outcome"] == "applied"]
    rejected = [payload for payload in payloads if payload["outcome"] == "generation_reuse_rejected"]
    assert len(applied) == 1
    assert len(rejected) == len(requests) - 1

    winner = applied[0]
    assert winner["accepted"] is True
    assert winner["state_changed"] is True
    assert winner["fencing_version"] == 2
    assert winner["resource_version"] == 2
    assert winner["value"] == winner["requested_value"]

    expected_winner = _expected_pair(
        counter=NEXT_COUNTER,
        version=2,
        mutation_id=str(winner["mutation_id"]),
        value=str(winner["requested_value"]),
    )

    for payload in rejected:
        assert payload["accepted"] is False
        assert payload["state_changed"] is False
        assert payload["fencing_version"] == 2
        assert payload["resource_version"] == 2
        assert payload["value"] == winner["requested_value"]

    for payload in payloads:
        assert payload["automatic_control_allowed"] is False
        assert payload["activation_allowed"] is False
        assert payload["traffic_switching_allowed"] is False
        assert payload["observed"] == expected_winner

    # Long-lived and newly reconstructed parent readers must agree on exactly the one
    # committed winner; no losing process may leave a partial rewrite behind.
    assert _pair_payload(reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected_winner
    fresh_reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=3.0)
    assert _pair_payload(fresh_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected_winner

    # Exact replay of the winning generation remains idempotent after contention.
    replay = writer.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        NEXT_COUNTER,
        mutation_id=str(winner["mutation_id"]),
        value=str(winner["requested_value"]),
    )
    assert replay.outcome == "idempotent"
    assert replay.accepted is True
    assert replay.state_changed is False
    assert replay.fencing_version == 2
    assert replay.resource_version == 2

    # Conflicting reuse of that committed generation still fails closed.
    conflict = writer.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        NEXT_COUNTER,
        mutation_id="mutation-402-conflict",
        value="conflicting-402",
    )
    assert conflict.outcome == "generation_reuse_rejected"
    assert conflict.accepted is False
    assert conflict.state_changed is False
    assert _pair_payload(reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected_winner

    # Process completion must release the exercised SQLite write lock.
    connection = sqlite3.connect(str(database), timeout=3.0, isolation_level=None)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.rollback()
    finally:
        connection.close()

    # The bounded contention event must not poison a later valid generation.
    successor = writer.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        NEXT_COUNTER + 1,
        mutation_id="mutation-403",
        value="committed-403",
    )
    assert successor.outcome == "applied"
    assert successor.accepted is True
    assert successor.state_changed is True
    assert successor.fencing_version == 3
    assert successor.resource_version == 3
    assert successor.automatic_control_allowed is False
    assert successor.activation_allowed is False
    assert successor.traffic_switching_allowed is False

    expected_successor = _expected_pair(
        counter=NEXT_COUNTER + 1,
        version=3,
        mutation_id="mutation-403",
        value="committed-403",
    )
    assert _pair_payload(reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected_successor
    assert _pair_payload(fresh_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected_successor


def test_concurrent_next_generation_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "production readiness" in combined
    assert "benchmark" in combined
    assert "novelty" in combined
