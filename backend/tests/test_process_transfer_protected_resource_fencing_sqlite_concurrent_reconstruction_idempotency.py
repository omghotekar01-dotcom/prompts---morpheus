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


RESOURCE_ID = "resource-concurrent-reconstruction-idempotency"
AUTHORITY_ID = "authority-concurrent-reconstruction-idempotency"
COMMITTED_COUNTER = 301
COMMITTED_MUTATION_ID = "mutation-301"
COMMITTED_VALUE = "committed-301"


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


def _race_worker(
    database: str,
    start: mp.Event,
    ready: mp.Queue,  # type: ignore[type-arg]
    output: mp.Queue,  # type: ignore[type-arg]
    mutation_id: str,
    value: str,
) -> None:
    try:
        writer = SQLiteTransactionallyFencedProtectedResource(database, timeout_seconds=2.0)
        reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=2.0)
        ready.put(True)
        if not start.wait(timeout=10.0):
            raise AssertionError("concurrent reconstruction start gate was not released")
        result = writer.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            COMMITTED_COUNTER,
            mutation_id=mutation_id,
            value=value,
        )
        observed = _pair_payload(reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID))
        output.put(
            {
                "ok": True,
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
        output.put({"ok": False, "error": repr(exc)})
        raise


def test_concurrent_spawn_replays_and_conflicts_preserve_committed_generation(tmp_path: Path) -> None:
    database = tmp_path / "concurrent-reconstruction-idempotency.sqlite3"
    writer = SQLiteTransactionallyFencedProtectedResource(database, timeout_seconds=2.0)
    reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=2.0)

    committed = writer.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        COMMITTED_COUNTER,
        mutation_id=COMMITTED_MUTATION_ID,
        value=COMMITTED_VALUE,
    )
    assert committed.outcome == "applied"
    assert committed.accepted is True
    assert committed.state_changed is True

    expected = _expected_pair(
        counter=COMMITTED_COUNTER,
        version=1,
        mutation_id=COMMITTED_MUTATION_ID,
        value=COMMITTED_VALUE,
    )
    assert _pair_payload(reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected

    # Each child reconstructs independent adapters from committed bytes before a shared
    # release gate. This exercises SQLite serialization rather than shared Python objects.
    context = mp.get_context("spawn")
    start = context.Event()
    ready = context.Queue()
    output = context.Queue()
    requests = [
        (COMMITTED_MUTATION_ID, COMMITTED_VALUE, "idempotent"),
        (COMMITTED_MUTATION_ID, COMMITTED_VALUE, "idempotent"),
        (COMMITTED_MUTATION_ID, "conflicting-value", "generation_reuse_rejected"),
        ("different-mutation", COMMITTED_VALUE, "generation_reuse_rejected"),
    ]
    children = [
        context.Process(target=_race_worker, args=(str(database), start, ready, output, mutation_id, value))
        for mutation_id, value, _ in requests
    ]
    for child in children:
        child.start()
    for _ in children:
        assert ready.get(timeout=10.0) is True
    start.set()

    for child in children:
        child.join(timeout=15.0)
        if child.is_alive():
            child.terminate()
            child.join(timeout=2.0)
            raise AssertionError("concurrent reconstruction child did not finish")
        assert child.exitcode == 0

    payloads = [output.get(timeout=2.0) for _ in children]
    assert all(payload["ok"] is True for payload in payloads), payloads
    outcomes = sorted(payload["outcome"] for payload in payloads)
    assert outcomes == ["generation_reuse_rejected", "generation_reuse_rejected", "idempotent", "idempotent"]

    for payload in payloads:
        if payload["outcome"] == "idempotent":
            assert payload["accepted"] is True
        else:
            assert payload["accepted"] is False
        assert payload["state_changed"] is False
        assert payload["fencing_version"] == 1
        assert payload["resource_version"] == 1
        assert payload["value"] == COMMITTED_VALUE
        assert payload["automatic_control_allowed"] is False
        assert payload["activation_allowed"] is False
        assert payload["traffic_switching_allowed"] is False
        assert payload["observed"] == expected

    # Parent and newly reconstructed readers must agree that contention never changed
    # or partially rewrote the committed generation.
    assert _pair_payload(reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
    fresh_reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=2.0)
    assert _pair_payload(fresh_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected

    # Process completion must release the exercised SQLite write lock.
    connection = sqlite3.connect(str(database), timeout=2.0, isolation_level=None)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.rollback()
    finally:
        connection.close()

    # Same-generation contention must not poison later valid local progress.
    successor = writer.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        COMMITTED_COUNTER + 1,
        mutation_id="mutation-302",
        value="committed-302",
    )
    assert successor.outcome == "applied"
    assert successor.accepted is True
    assert successor.state_changed is True
    assert successor.fencing_version == 2
    assert successor.resource_version == 2
    assert successor.automatic_control_allowed is False
    assert successor.activation_allowed is False
    assert successor.traffic_switching_allowed is False

    expected_successor = _expected_pair(
        counter=COMMITTED_COUNTER + 1,
        version=2,
        mutation_id="mutation-302",
        value="committed-302",
    )
    assert _pair_payload(reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected_successor
    assert _pair_payload(fresh_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected_successor


def test_concurrent_reconstruction_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "production readiness" in combined
    assert "benchmark" in combined
    assert "novelty" in combined
