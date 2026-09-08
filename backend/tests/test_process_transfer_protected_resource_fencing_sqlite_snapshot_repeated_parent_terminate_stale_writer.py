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


RESOURCE_ID = "resource-schema-repeated-parent-terminate-stale-writer"
AUTHORITY_ID = "authority-schema-repeated-parent-terminate-stale-writer"
PRESERVED_TABLE = "morpheus_protected_resource_state_during_repeated_parent_terminate_stale_writer"


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

    # This path exists only for bounded teardown if a parent assertion fails. The
    # exercised success path terminates the child before this wait is released.
    try:
        release.wait(30.0)
    finally:
        if connection.in_transaction:
            connection.rollback()
        connection.close()


def _terminate_one_staged_child(database: Path) -> None:
    context = mp.get_context("spawn")
    staged = context.Event()
    release = context.Event()
    child = context.Process(
        target=_stage_incompatible_replacement_and_wait,
        args=(str(database), staged, release),
    )
    child.start()
    try:
        assert staged.wait(5.0), "stale-writer gate child did not stage schema replacement"
        child.terminate()
        child.join(timeout=5.0)
        assert not child.is_alive(), "stale-writer gate child did not terminate"
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


def _assert_committed_state_and_writer_available(
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
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert "morpheus_protected_resource_state" in tables
        assert PRESERVED_TABLE not in tables

        columns = {
            row[1]
            for row in connection.execute(
                'PRAGMA table_info("morpheus_protected_resource_state")'
            ).fetchall()
        }
        assert "last_mutation_id" in columns

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

        # This is a bounded lock-release assertion, not a latency or throughput claim.
        connection.execute("BEGIN IMMEDIATE")
        connection.rollback()
    finally:
        connection.close()


def test_repeated_termination_recovery_rejects_retained_stale_writer_tokens(
    tmp_path: Path,
) -> None:
    database = tmp_path / "snapshot-repeated-parent-terminate-stale-writer.sqlite3"
    resource = SQLiteTransactionallyFencedProtectedResource(database)

    seeded = resource.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        91,
        mutation_id="mutation-91",
        value="committed-91",
    )
    assert seeded.outcome == "applied"
    assert seeded.accepted is True
    assert seeded.state_changed is True

    long_lived_reader = SQLiteTransactionConsistentFencingResourceReader(
        database, timeout_seconds=1.0
    )

    counter = 91
    version = 1
    for cycle in range(3):
        current_mutation_id = f"mutation-{counter}"
        current_value = f"committed-{counter}"
        _assert_pair(
            long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
            counter=counter,
            version=version,
            mutation_id=current_mutation_id,
            value=current_value,
        )

        retained_stale_counter = counter
        _terminate_one_staged_child(database)

        _assert_committed_state_and_writer_available(
            database,
            counter=counter,
            version=version,
            mutation_id=current_mutation_id,
            value=current_value,
        )

        # Recovery must expose the last committed pair before any successor mutation.
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
        successor = resource.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            successor_counter,
            mutation_id=successor_mutation_id,
            value=successor_value,
        )
        assert successor.outcome == "applied"
        assert successor.accepted is True
        assert successor.state_changed is True

        counter = successor_counter
        version += 1
        _assert_pair(
            long_lived_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
            counter=counter,
            version=version,
            mutation_id=successor_mutation_id,
            value=successor_value,
        )
        _assert_pair(
            fresh_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
            counter=counter,
            version=version,
            mutation_id=successor_mutation_id,
            value=successor_value,
        )

        # The retained token was current before recovery but is stale after the valid
        # successor. It must not alter fencing state or protected-resource state.
        stale = resource.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            retained_stale_counter,
            mutation_id=f"stale-attempt-{cycle}",
            value=f"must-not-commit-{cycle}",
        )
        assert stale.outcome == "stale"
        assert stale.accepted is False
        assert stale.state_changed is False
        assert stale.requested_fencing_counter == retained_stale_counter
        assert stale.fencing_version == version
        assert stale.resource_version == version
        assert stale.value == successor_value
        assert stale.automatic_control_allowed is False
        assert stale.activation_allowed is False
        assert stale.traffic_switching_allowed is False

        # Rejection must preserve every current committed field, including mutation
        # identity, while leaving the database writable for the next exercised cycle.
        _assert_committed_state_and_writer_available(
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
        post_rejection_reader = SQLiteTransactionConsistentFencingResourceReader(
            database, timeout_seconds=1.0
        )
        _assert_pair(
            post_rejection_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
            counter=counter,
            version=version,
            mutation_id=successor_mutation_id,
            value=successor_value,
        )

        # Three deterministic cycles are regression evidence only, not a soak test or
        # statistical reliability, availability, scalability, or performance evidence.
        assert cycle < 3

    assert counter == 94
    assert version == 4


def test_repeated_termination_stale_writer_gate_does_not_expand_truth_claims() -> None:
    assert "power-loss durability" in TRUTH_BOUNDARY
    assert "security boundary" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark" in TRUTH_BOUNDARY
    assert "novelty" in TRUTH_BOUNDARY
