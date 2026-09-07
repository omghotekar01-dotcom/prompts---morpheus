from __future__ import annotations

import multiprocessing as mp
import os
from pathlib import Path
from typing import Any

from app.process_transfer_protected_resource_fencing_sqlite import SQLiteAtomicConditionalFencingBackend
from app.process_transfer_protected_resource_fencing_sqlite_resource import (
    SQLiteTransactionallyFencedProtectedResource,
)


TRUTH_BOUNDARY = (
    "These tests provide local-host SQLite ambiguous-commit-outcome retry evidence only. "
    "They do not establish exactly-once delivery, distributed transaction semantics, external-resource idempotency, "
    "power-loss durability, production failover, activation authority, traffic-switching authority, HA/SLA behavior, "
    "or production readiness."
)


def _commit_then_exit_without_ack(
    database_path: str,
    *,
    fencing_counter: int,
    mutation_id: str,
    value: str,
    started: Any,
) -> None:
    resource = SQLiteTransactionallyFencedProtectedResource(database_path)
    started.send("mutation-started")
    started.close()
    result = resource.mutate(
        "resource-a",
        "authority-a",
        fencing_counter,
        mutation_id=mutation_id,
        value=value,
    )
    if result.outcome != "applied" or not result.accepted or not result.state_changed:
        os._exit(91)
    # Deliberately terminate after SQLite commit and after mutate() has produced its
    # result, but before any result/acknowledgement is delivered to the parent.
    os._exit(23)


def _run_ambiguous_commit(
    ctx: mp.context.BaseContext,
    database_path: str,
    *,
    fencing_counter: int,
    mutation_id: str,
    value: str,
) -> None:
    parent_started, child_started = ctx.Pipe(duplex=False)
    process = ctx.Process(
        target=_commit_then_exit_without_ack,
        kwargs={
            "database_path": database_path,
            "fencing_counter": fencing_counter,
            "mutation_id": mutation_id,
            "value": value,
            "started": child_started,
        },
    )
    process.start()
    child_started.close()
    assert parent_started.poll(10), "child did not begin the ambiguous-outcome mutation"
    assert parent_started.recv() == "mutation-started"
    parent_started.close()
    process.join(timeout=15)
    assert not process.is_alive()
    assert process.exitcode == 23


def _assert_fencing_resource_agreement(database_path: str, expected_counter: int, expected_version: int) -> None:
    fencing = SQLiteAtomicConditionalFencingBackend(database_path).snapshot("resource-a", "authority-a")
    resource = SQLiteTransactionallyFencedProtectedResource(database_path).snapshot("resource-a", "authority-a")
    assert fencing is not None and resource is not None
    assert fencing.fencing_counter == expected_counter
    assert fencing.version == expected_version
    assert resource.last_fencing_counter == expected_counter
    assert resource.resource_version == expected_version


def test_first_commit_with_lost_ack_is_retry_safe_and_generation_reuse_fails_closed(tmp_path: Path) -> None:
    ctx = mp.get_context("spawn")
    database = str(tmp_path / "fencing.sqlite3")
    # Initialize schemas before spawning so the evidence focuses on the mutation outcome.
    SQLiteTransactionallyFencedProtectedResource(database)

    _run_ambiguous_commit(ctx, database, fencing_counter=1, mutation_id="m-1", value="alpha")

    reconstructed = SQLiteTransactionallyFencedProtectedResource(database)
    committed = reconstructed.snapshot("resource-a", "authority-a")
    assert committed is not None
    assert (committed.value, committed.last_mutation_id, committed.last_fencing_counter, committed.resource_version) == (
        "alpha",
        "m-1",
        1,
        1,
    )

    retry = reconstructed.mutate("resource-a", "authority-a", 1, mutation_id="m-1", value="alpha")
    assert retry.outcome == "idempotent"
    assert retry.accepted is True
    assert retry.state_changed is False
    assert retry.fencing_version == 1
    assert retry.resource_version == 1
    assert retry.automatic_control_allowed is False
    assert retry.activation_allowed is False
    assert retry.traffic_switching_allowed is False

    different_id = reconstructed.mutate("resource-a", "authority-a", 1, mutation_id="m-other", value="alpha")
    assert different_id.outcome == "generation_reuse_rejected"
    assert different_id.accepted is False
    assert different_id.state_changed is False

    different_value = reconstructed.mutate("resource-a", "authority-a", 1, mutation_id="m-1", value="changed")
    assert different_value.outcome == "generation_reuse_rejected"
    assert different_value.accepted is False
    assert different_value.state_changed is False

    _assert_fencing_resource_agreement(database, expected_counter=1, expected_version=1)

    newer = reconstructed.mutate("resource-a", "authority-a", 2, mutation_id="m-2", value="beta")
    assert newer.outcome == "applied"
    assert newer.accepted is True
    assert newer.state_changed is True
    _assert_fencing_resource_agreement(database, expected_counter=2, expected_version=2)


def test_newer_commit_with_lost_ack_preserves_stale_and_retry_semantics(tmp_path: Path) -> None:
    ctx = mp.get_context("spawn")
    database = str(tmp_path / "fencing.sqlite3")
    resource = SQLiteTransactionallyFencedProtectedResource(database)
    first = resource.mutate("resource-a", "authority-a", 4, mutation_id="m-4", value="alpha")
    assert first.outcome == "applied"

    _run_ambiguous_commit(ctx, database, fencing_counter=7, mutation_id="m-7", value="gamma")

    reconstructed = SQLiteTransactionallyFencedProtectedResource(database)
    _assert_fencing_resource_agreement(database, expected_counter=7, expected_version=2)

    retry = reconstructed.mutate("resource-a", "authority-a", 7, mutation_id="m-7", value="gamma")
    assert retry.outcome == "idempotent"
    assert retry.accepted is True
    assert retry.state_changed is False
    assert retry.fencing_version == 2
    assert retry.resource_version == 2

    stale = reconstructed.mutate("resource-a", "authority-a", 6, mutation_id="m-6", value="stale")
    assert stale.outcome == "stale"
    assert stale.accepted is False
    assert stale.state_changed is False

    reused = reconstructed.mutate("resource-a", "authority-a", 7, mutation_id="m-7-other", value="gamma")
    assert reused.outcome == "generation_reuse_rejected"
    assert reused.accepted is False
    assert reused.state_changed is False

    _assert_fencing_resource_agreement(database, expected_counter=7, expected_version=2)
    assert "local-host SQLite ambiguous-commit-outcome retry evidence only" in TRUTH_BOUNDARY
    assert "exactly-once delivery" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
