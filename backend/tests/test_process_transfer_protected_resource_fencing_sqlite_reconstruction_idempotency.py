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


RESOURCE_ID = "resource-reconstruction-idempotency"
AUTHORITY_ID = "authority-reconstruction-idempotency"
COMMITTED_COUNTER = 201
COMMITTED_MUTATION_ID = "mutation-201"
COMMITTED_VALUE = "committed-201"


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


def _result_payload(result) -> dict[str, object]:  # type: ignore[no-untyped-def]
    return {
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


def _reconstruct_and_exercise_in_child(database: str, output: mp.Queue) -> None:  # type: ignore[type-arg]
    try:
        writer = SQLiteTransactionallyFencedProtectedResource(database, timeout_seconds=1.0)
        reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=1.0)

        before = _pair_payload(reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID))
        replay = writer.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            COMMITTED_COUNTER,
            mutation_id=COMMITTED_MUTATION_ID,
            value=COMMITTED_VALUE,
        )
        value_conflict = writer.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            COMMITTED_COUNTER,
            mutation_id=COMMITTED_MUTATION_ID,
            value="child-conflicting-value",
        )
        identity_conflict = writer.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            COMMITTED_COUNTER,
            mutation_id="child-different-mutation",
            value=COMMITTED_VALUE,
        )
        after = _pair_payload(reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID))
        output.put(
            {
                "ok": True,
                "before": before,
                "replay": _result_payload(replay),
                "value_conflict": _result_payload(value_conflict),
                "identity_conflict": _result_payload(identity_conflict),
                "after": after,
            }
        )
    except Exception as exc:  # pragma: no cover - surfaced through parent assertion
        output.put({"ok": False, "error": repr(exc)})
        raise


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


def _assert_idempotent(payload: dict[str, object], *, version: int, value: str) -> None:
    assert payload == {
        "outcome": "idempotent",
        "accepted": True,
        "state_changed": False,
        "fencing_version": version,
        "resource_version": version,
        "value": value,
        "automatic_control_allowed": False,
        "activation_allowed": False,
        "traffic_switching_allowed": False,
    }


def _assert_rejected(payload: dict[str, object], *, version: int, value: str) -> None:
    assert payload == {
        "outcome": "generation_reuse_rejected",
        "accepted": False,
        "state_changed": False,
        "fencing_version": version,
        "resource_version": version,
        "value": value,
        "automatic_control_allowed": False,
        "activation_allowed": False,
        "traffic_switching_allowed": False,
    }


def test_committed_idempotency_persists_across_parent_and_spawn_reconstruction(
    tmp_path: Path,
) -> None:
    database = tmp_path / "reconstruction-idempotency.sqlite3"

    initial_writer = SQLiteTransactionallyFencedProtectedResource(database, timeout_seconds=1.0)
    committed = initial_writer.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        COMMITTED_COUNTER,
        mutation_id=COMMITTED_MUTATION_ID,
        value=COMMITTED_VALUE,
    )
    assert committed.outcome == "applied"
    assert committed.accepted is True
    assert committed.state_changed is True
    assert committed.fencing_version == 1
    assert committed.resource_version == 1

    initial_reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=1.0)
    assert _pair_payload(initial_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == _expected_pair(
        counter=COMMITTED_COUNTER,
        version=1,
        mutation_id=COMMITTED_MUTATION_ID,
        value=COMMITTED_VALUE,
    )

    # Dispose of the objects that produced and first observed the commit. The adapters
    # hold no persistent SQLite connection; reconstruction must rely on committed bytes.
    del initial_reader
    del initial_writer

    parent_writer = SQLiteTransactionallyFencedProtectedResource(database, timeout_seconds=1.0)
    parent_reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=1.0)

    parent_before = _pair_payload(parent_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID))
    assert parent_before == _expected_pair(
        counter=COMMITTED_COUNTER,
        version=1,
        mutation_id=COMMITTED_MUTATION_ID,
        value=COMMITTED_VALUE,
    )

    parent_replay = _result_payload(
        parent_writer.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            COMMITTED_COUNTER,
            mutation_id=COMMITTED_MUTATION_ID,
            value=COMMITTED_VALUE,
        )
    )
    _assert_idempotent(parent_replay, version=1, value=COMMITTED_VALUE)

    parent_value_conflict = _result_payload(
        parent_writer.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            COMMITTED_COUNTER,
            mutation_id=COMMITTED_MUTATION_ID,
            value="parent-conflicting-value",
        )
    )
    _assert_rejected(parent_value_conflict, version=1, value=COMMITTED_VALUE)

    parent_identity_conflict = _result_payload(
        parent_writer.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            COMMITTED_COUNTER,
            mutation_id="parent-different-mutation",
            value=COMMITTED_VALUE,
        )
    )
    _assert_rejected(parent_identity_conflict, version=1, value=COMMITTED_VALUE)

    assert _pair_payload(parent_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == parent_before

    context = mp.get_context("spawn")
    output = context.Queue()
    child = context.Process(target=_reconstruct_and_exercise_in_child, args=(str(database), output))
    child.start()
    child.join(timeout=10.0)
    if child.is_alive():
        child.terminate()
        child.join(timeout=2.0)
        raise AssertionError("reconstruction idempotency child did not finish")
    assert child.exitcode == 0
    child_payload = output.get(timeout=2.0)
    assert child_payload["ok"] is True, child_payload

    assert child_payload["before"] == parent_before
    _assert_idempotent(child_payload["replay"], version=1, value=COMMITTED_VALUE)
    _assert_rejected(child_payload["value_conflict"], version=1, value=COMMITTED_VALUE)
    _assert_rejected(child_payload["identity_conflict"], version=1, value=COMMITTED_VALUE)
    assert child_payload["after"] == parent_before

    # Parent and spawned-process reconstruction must leave the same committed pair.
    assert _pair_payload(parent_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == parent_before
    post_child_reader = SQLiteTransactionConsistentFencingResourceReader(database, timeout_seconds=1.0)
    assert _pair_payload(post_child_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == parent_before

    # Idempotency/conflict handling must not poison later valid local progress.
    successor = parent_writer.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        COMMITTED_COUNTER + 1,
        mutation_id="mutation-202",
        value="committed-202",
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
        mutation_id="mutation-202",
        value="committed-202",
    )
    assert _pair_payload(parent_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected_successor
    assert _pair_payload(post_child_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)) == expected_successor


def test_reconstruction_idempotency_gate_does_not_expand_truth_claims() -> None:
    combined = f"{RESOURCE_TRUTH_BOUNDARY} {READER_TRUTH_BOUNDARY}"
    assert "distributed" in combined
    assert "power-loss" in combined
    assert "production readiness" in combined
    assert "benchmark" in combined
    assert "novelty" in combined
