from __future__ import annotations

import multiprocessing as mp
from pathlib import Path
import sqlite3

from app.process_transfer_protected_resource_fencing_sqlite_resource import (
    SQLiteTransactionallyFencedProtectedResource,
)
from app.process_transfer_protected_resource_fencing_sqlite_snapshot import (
    SQLiteTransactionConsistentFencingResourceReader,
    TRUTH_BOUNDARY,
)


RESOURCE_ID = "resource-recovery-idempotency"
AUTHORITY_ID = "authority-recovery-idempotency"
PRESERVED_TABLE = "morpheus_protected_resource_state_during_recovery_idempotency"


def _stage_incompatible_replacement_and_wait(
    database: str,
    staged: mp.synchronize.Event,
    release: mp.synchronize.Event,
) -> None:
    connection = sqlite3.connect(database, timeout=2.0, isolation_level=None)
    connection.execute("PRAGMA busy_timeout = 2000")
    connection.execute("BEGIN IMMEDIATE")
    connection.execute(
        "ALTER TABLE morpheus_protected_resource_state "
        f"RENAME TO {PRESERVED_TABLE}"
    )
    connection.execute(
        """
        CREATE TABLE morpheus_protected_resource_state (
            resource_id TEXT NOT NULL,
            fencing_authority_id TEXT NOT NULL,
            resource_version INTEGER NOT NULL,
            value TEXT NOT NULL,
            last_fencing_counter INTEGER NOT NULL,
            PRIMARY KEY (resource_id, fencing_authority_id)
        )
        """
    )
    staged.set()
    try:
        release.wait(30.0)
    finally:
        if connection.in_transaction:
            connection.rollback()
        connection.close()


def _terminate_staged_child(database: Path) -> None:
    context = mp.get_context("spawn")
    staged = context.Event()
    release = context.Event()
    child = context.Process(
        target=_stage_incompatible_replacement_and_wait,
        args=(str(database), staged, release),
    )
    child.start()
    try:
        assert staged.wait(5.0), "idempotency gate child did not stage schema replacement"
        child.terminate()
        child.join(timeout=5.0)
        assert not child.is_alive(), "idempotency gate child did not terminate"
        assert child.exitcode is not None
    finally:
        if child.is_alive():
            release.set()
            child.join(timeout=2.0)
        if child.is_alive():
            child.terminate()
            child.join(timeout=2.0)


def _assert_pair(
    pair,  # type: ignore[no-untyped-def]
    *,
    counter: int,
    version: int,
    mutation_id: str,
    value: str,
) -> None:
    assert pair is not None
    assert pair.fencing.fencing_counter == counter
    assert pair.fencing.version == version
    assert pair.resource.resource_version == version
    assert pair.resource.value == value
    assert pair.resource.last_mutation_id == mutation_id
    assert pair.resource.last_fencing_counter == counter
    assert pair.fencing.fencing_counter == pair.resource.last_fencing_counter
    assert pair.fencing.version == pair.resource.resource_version
    assert pair.automatic_control_allowed is False
    assert pair.activation_allowed is False
    assert pair.traffic_switching_allowed is False


def _assert_persisted_pair_and_writer_available(
    database: Path,
    *,
    counter: int,
    version: int,
    mutation_id: str,
    value: str,
) -> None:
    connection = sqlite3.connect(database, timeout=1.0, isolation_level=None)
    try:
        connection.execute("PRAGMA busy_timeout = 1000")
        fencing = connection.execute(
            "SELECT fencing_counter, version FROM morpheus_fencing_state "
            "WHERE resource_id = ? AND fencing_authority_id = ?",
            (RESOURCE_ID, AUTHORITY_ID),
        ).fetchone()
        resource = connection.execute(
            "SELECT resource_version, value, last_mutation_id, last_fencing_counter "
            "FROM morpheus_protected_resource_state "
            "WHERE resource_id = ? AND fencing_authority_id = ?",
            (RESOURCE_ID, AUTHORITY_ID),
        ).fetchone()
        assert fencing == (counter, version)
        assert resource == (version, value, mutation_id, counter)

        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert PRESERVED_TABLE not in tables

        # Bounded lock-release evidence only; this is not a latency/performance claim.
        connection.execute("BEGIN IMMEDIATE")
        connection.rollback()
    finally:
        connection.close()


def test_recovered_generation_preserves_idempotent_retry_and_rejects_conflict(
    tmp_path: Path,
) -> None:
    database = tmp_path / "snapshot-recovery-idempotency.sqlite3"
    resource = SQLiteTransactionallyFencedProtectedResource(database)

    seeded = resource.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        101,
        mutation_id="mutation-101",
        value="committed-101",
    )
    assert seeded.outcome == "applied"
    assert seeded.accepted is True
    assert seeded.state_changed is True

    long_lived_reader = SQLiteTransactionConsistentFencingResourceReader(
        database, timeout_seconds=1.0
    )

    # Exercise two deterministic recovered generations. This is regression evidence,
    # not soak testing or a reliability-rate/availability measurement.
    counter = 101
    version = 1
    for cycle in range(2):
        _terminate_staged_child(database)

        current_mutation_id = f"mutation-{counter}"
        current_value = f"committed-{counter}"
        _assert_persisted_pair_and_writer_available(
            database,
            counter=counter,
            version=version,
            mutation_id=current_mutation_id,
            value=current_value,
        )

        fresh_reader = SQLiteTransactionConsistentFencingResourceReader(
            database, timeout_seconds=1.0
        )
        _assert_pair(
            long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
            counter=counter,
            version=version,
            mutation_id=current_mutation_id,
            value=current_value,
        )
        _assert_pair(
            fresh_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
            counter=counter,
            version=version,
            mutation_id=current_mutation_id,
            value=current_value,
        )

        successor_counter = counter + 1
        successor_mutation_id = f"mutation-{successor_counter}"
        successor_value = f"committed-{successor_counter}"
        applied = resource.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            successor_counter,
            mutation_id=successor_mutation_id,
            value=successor_value,
        )
        assert applied.outcome == "applied"
        assert applied.accepted is True
        assert applied.state_changed is True

        counter = successor_counter
        version += 1

        # Exact replay of the committed mutation at the same fencing generation is
        # idempotent: accepted, but it must not advance either version or alter state.
        replay = resource.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            counter,
            mutation_id=successor_mutation_id,
            value=successor_value,
        )
        assert replay.outcome == "idempotent"
        assert replay.accepted is True
        assert replay.state_changed is False
        assert replay.fencing_version == version
        assert replay.resource_version == version
        assert replay.value == successor_value
        assert replay.automatic_control_allowed is False
        assert replay.activation_allowed is False
        assert replay.traffic_switching_allowed is False

        _assert_persisted_pair_and_writer_available(
            database,
            counter=counter,
            version=version,
            mutation_id=successor_mutation_id,
            value=successor_value,
        )

        # Reusing the same committed mutation identity/generation with a different
        # value is not an idempotent retry and must fail closed without mutation.
        conflict = resource.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            counter,
            mutation_id=successor_mutation_id,
            value=f"conflicting-value-{cycle}",
        )
        assert conflict.outcome == "generation_reuse_rejected"
        assert conflict.accepted is False
        assert conflict.state_changed is False
        assert conflict.fencing_version == version
        assert conflict.resource_version == version
        assert conflict.value == successor_value
        assert conflict.automatic_control_allowed is False
        assert conflict.activation_allowed is False
        assert conflict.traffic_switching_allowed is False

        # A different mutation identity at the same fencing generation is likewise
        # rejected, preserving the already-committed mutation identity and value.
        identity_conflict = resource.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            counter,
            mutation_id=f"different-mutation-{cycle}",
            value=successor_value,
        )
        assert identity_conflict.outcome == "generation_reuse_rejected"
        assert identity_conflict.accepted is False
        assert identity_conflict.state_changed is False
        assert identity_conflict.fencing_version == version
        assert identity_conflict.resource_version == version
        assert identity_conflict.value == successor_value

        _assert_persisted_pair_and_writer_available(
            database,
            counter=counter,
            version=version,
            mutation_id=successor_mutation_id,
            value=successor_value,
        )
        _assert_pair(
            long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
            counter=counter,
            version=version,
            mutation_id=successor_mutation_id,
            value=successor_value,
        )
        post_conflict_reader = SQLiteTransactionConsistentFencingResourceReader(
            database, timeout_seconds=1.0
        )
        _assert_pair(
            post_conflict_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
            counter=counter,
            version=version,
            mutation_id=successor_mutation_id,
            value=successor_value,
        )

    # Prove rejection/idempotency did not poison later valid progress.
    final = resource.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        counter + 1,
        mutation_id=f"mutation-{counter + 1}",
        value=f"committed-{counter + 1}",
    )
    assert final.outcome == "applied"
    assert final.accepted is True
    assert final.state_changed is True
    assert final.fencing_version == version + 1
    assert final.resource_version == version + 1

    _assert_pair(
        long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
        counter=counter + 1,
        version=version + 1,
        mutation_id=f"mutation-{counter + 1}",
        value=f"committed-{counter + 1}",
    )


def test_recovery_idempotency_gate_does_not_expand_truth_claims() -> None:
    assert "power-loss" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark" in TRUTH_BOUNDARY
    assert "novelty" in TRUTH_BOUNDARY
