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


RESOURCE_ID = "resource-repeated-mixed-generation"
AUTHORITY_ID = "authority-repeated-mixed-generation"
BASE_COUNTER = 701
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


def _mixed_round_worker(
    database: str,
    start: mp.Event,
    observe: mp.Event,
    ready: mp.Queue,  # type: ignore[type-arg]
    mutations: mp.Queue,  # type: ignore[type-arg]
    observations: mp.Queue,  # type: ignore[type-arg]
    label: str,
    counter: int,
    mutation_id: str,
    value: str,
) -> None:
    try:
        writer = SQLiteTransactionallyFencedProtectedResource(database, timeout_seconds=3.0)
        reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=3.0)
        ready.put(label)
        if not start.wait(timeout=10.0):
            raise AssertionError("repeated mixed-generation start gate was not released")

        result = writer.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            counter,
            mutation_id=mutation_id,
            value=value,
        )
        mutations.put(
            {
                "ok": True,
                "label": label,
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
            }
        )

        if not observe.wait(timeout=10.0):
            raise AssertionError("repeated mixed-generation observation gate was not released")
        observations.put(
            {
                "ok": True,
                "label": label,
                "observed": _pair_payload(reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)),
            }
        )
    except Exception as exc:  # pragma: no cover - surfaced through parent assertion
        mutations.put({"ok": False, "label": label, "error": repr(exc)})
        raise


def _assert_write_lock_released(database: Path) -> None:
    connection = sqlite3.connect(str(database), timeout=3.0, isolation_level=None)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.rollback()
    finally:
        connection.close()


def test_repeated_spawned_mixed_generation_contention_advances_monotonically(tmp_path: Path) -> None:
    database = tmp_path / "repeated-mixed-generation.sqlite3"
    writer = SQLiteTransactionallyFencedProtectedResource(database, timeout_seconds=3.0)
    long_lived_reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=3.0)

    base_mutation_id = f"mutation-{BASE_COUNTER}"
    base_value = f"committed-{BASE_COUNTER}"
    base = writer.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        BASE_COUNTER,
        mutation_id=base_mutation_id,
        value=base_value,
    )
    assert base.outcome == "applied"
    assert base.accepted is True
    assert base.state_changed is True

    expected = _expected_pair(
        counter=BASE_COUNTER,
        version=1,
        mutation_id=base_mutation_id,
        value=base_value,
    )
    assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected

    current_counter = BASE_COUNTER
    current_mutation_id = base_mutation_id
    current_value = base_value
    context = mp.get_context("spawn")

    for round_index in range(1, ROUNDS + 1):
        next_counter = current_counter + 1
        expected_version = round_index + 1
        stale_counter = current_counter - 1
        start = context.Event()
        observe = context.Event()
        ready = context.Queue()
        mutations = context.Queue()
        observations = context.Queue()

        requests = [
            ("stale", stale_counter, f"mutation-{stale_counter}-retained", f"retained-{stale_counter}"),
            ("current-replay", current_counter, current_mutation_id, current_value),
            (
                "current-conflict",
                current_counter,
                f"{current_mutation_id}-conflict",
                f"conflict-{current_counter}",
            ),
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
        ready_labels = {ready.get(timeout=10.0) for _ in children}
        assert ready_labels == {request[0] for request in requests}
        start.set()

        payloads = [mutations.get(timeout=15.0) for _ in children]
        assert all(payload["ok"] is True for payload in payloads), payloads
        by_label = {str(payload["label"]): payload for payload in payloads}

        stale = by_label["stale"]
        assert stale["outcome"] == "stale"
        assert stale["accepted"] is False
        assert stale["state_changed"] is False
        assert stale["fencing_version"] in {expected_version - 1, expected_version}
        assert stale["resource_version"] in {expected_version - 1, expected_version}

        replay = by_label["current-replay"]
        assert replay["outcome"] in {"idempotent", "stale"}
        assert replay["state_changed"] is False
        if replay["outcome"] == "idempotent":
            assert replay["accepted"] is True
            assert replay["fencing_version"] == expected_version - 1
            assert replay["resource_version"] == expected_version - 1
            assert replay["value"] == current_value
        else:
            assert replay["accepted"] is False
            assert replay["fencing_version"] == expected_version
            assert replay["resource_version"] == expected_version

        conflict = by_label["current-conflict"]
        assert conflict["outcome"] in {"generation_reuse_rejected", "stale"}
        assert conflict["accepted"] is False
        assert conflict["state_changed"] is False
        if conflict["outcome"] == "generation_reuse_rejected":
            assert conflict["fencing_version"] == expected_version - 1
            assert conflict["resource_version"] == expected_version - 1
            assert conflict["value"] == current_value
        else:
            assert conflict["fencing_version"] == expected_version
            assert conflict["resource_version"] == expected_version

        next_payloads = [by_label[f"next-{suffix}"] for suffix in ("a", "b", "c", "d")]
        applied = [payload for payload in next_payloads if payload["outcome"] == "applied"]
        rejected = [
            payload for payload in next_payloads if payload["outcome"] == "generation_reuse_rejected"
        ]
        assert len(applied) == 1
        assert len(rejected) == NEXT_CONTENDERS - 1

        winner = applied[0]
        assert winner["accepted"] is True
        assert winner["state_changed"] is True
        assert winner["fencing_version"] == expected_version
        assert winner["resource_version"] == expected_version
        assert winner["value"] == winner["requested_value"]

        expected = _expected_pair(
            counter=next_counter,
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

        observe.set()
        for child in children:
            child.join(timeout=20.0)
            if child.is_alive():
                child.terminate()
                child.join(timeout=2.0)
                raise AssertionError(f"repeated mixed-generation child did not finish in round {round_index}")
            assert child.exitcode == 0

        observed_payloads = [observations.get(timeout=2.0) for _ in children]
        assert all(payload["ok"] is True for payload in observed_payloads), observed_payloads
        assert all(payload["observed"] == expected for payload in observed_payloads)
        assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
        fresh_reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=3.0)
        assert _pair_payload(fresh_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
        _assert_write_lock_released(database)

        superseded = writer.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            current_counter,
            mutation_id=current_mutation_id,
            value=current_value,
        )
        assert superseded.outcome == "stale"
        assert superseded.accepted is False
        assert superseded.state_changed is False
        assert superseded.fencing_version == expected_version
        assert superseded.resource_version == expected_version
        assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected

        replay_winner = writer.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            next_counter,
            mutation_id=str(winner["mutation_id"]),
            value=str(winner["requested_value"]),
        )
        assert replay_winner.outcome == "idempotent"
        assert replay_winner.accepted is True
        assert replay_winner.state_changed is False
        assert replay_winner.fencing_version == expected_version
        assert replay_winner.resource_version == expected_version
        assert _pair_payload(fresh_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected
        _assert_write_lock_released(database)

        current_counter = next_counter
        current_mutation_id = str(winner["mutation_id"])
        current_value = str(winner["requested_value"])

    successor_counter = current_counter + 1
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

    final_pair = _expected_pair(
        counter=successor_counter,
        version=successor_version,
        mutation_id=f"mutation-{successor_counter}",
        value=f"committed-{successor_counter}",
    )
    assert _pair_payload(long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == final_pair
    final_reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=3.0)
    assert _pair_payload(final_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == final_pair
    _assert_write_lock_released(database)


def test_repeated_mixed_generation_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "production readiness" in combined
    assert "benchmark" in combined
    assert "novelty" in combined
