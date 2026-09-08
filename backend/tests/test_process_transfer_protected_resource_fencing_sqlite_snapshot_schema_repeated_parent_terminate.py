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


RESOURCE_ID = "resource-schema-repeated-parent-terminate"
AUTHORITY_ID = "authority-schema-repeated-parent-terminate"
PRESERVED_TABLE = "morpheus_protected_resource_state_during_repeated_parent_terminate"


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

    # The normal path exists only for bounded teardown if the parent assertion path
    # fails. The exercised success path terminates this process externally.
    try:
        release.wait(30.0)
    finally:
        if connection.in_transaction:
            connection.rollback()
        connection.close()


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
    assert pair.resource.last_mutation_id == mutation_id
    assert pair.resource.last_fencing_counter == counter
    assert pair.resource.value == value
    assert pair.fencing.fencing_counter == pair.resource.last_fencing_counter
    assert pair.fencing.version == pair.resource.resource_version
    assert pair.automatic_control_allowed is False
    assert pair.activation_allowed is False
    assert pair.traffic_switching_allowed is False


def _assert_committed_schema_state_and_writer_available(
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

        # A successful immediate transaction proves the terminated child did not leave
        # the exercised SQLite write lock blocking later local writers.
        connection.execute("BEGIN IMMEDIATE")
        connection.rollback()
    finally:
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
        assert staged.wait(5.0), "schema repeated-parent-terminate child did not stage replacement"
        child.terminate()
        child.join(timeout=5.0)
        assert not child.is_alive(), "schema repeated-parent-terminate child did not terminate"
        assert child.exitcode is not None
    finally:
        if child.is_alive():
            release.set()
            child.join(timeout=2.0)
        if child.is_alive():
            child.terminate()
            child.join(timeout=2.0)


def test_repeated_parent_termination_contains_schema_replacement_and_allows_monotonic_recovery(
    tmp_path: Path,
) -> None:
    database = tmp_path / "snapshot-schema-repeated-parent-terminate.sqlite3"
    resource = SQLiteTransactionallyFencedProtectedResource(database)

    seeded = resource.mutate(
        RESOURCE_ID,
        AUTHORITY_ID,
        71,
        mutation_id="mutation-71",
        value="committed-71",
    )
    assert seeded.outcome == "applied"
    assert seeded.state_changed is True

    stale_reader = SQLiteTransactionConsistentFencingResourceReader(
        database, timeout_seconds=1.0
    )

    counter = 71
    version = 1
    for cycle in range(3):
        mutation_id = f"mutation-{counter}"
        value = f"committed-{counter}"
        _assert_pair(
            stale_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
            counter=counter,
            version=version,
            mutation_id=mutation_id,
            value=value,
        )

        _terminate_one_staged_child(database)

        _assert_committed_schema_state_and_writer_available(
            database,
            counter=counter,
            version=version,
            mutation_id=mutation_id,
            value=value,
        )

        # Because the incompatible DDL never committed, both a long-lived reader and a
        # newly constructed reader must still expose only the current committed pair.
        _assert_pair(
            stale_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
            counter=counter,
            version=version,
            mutation_id=mutation_id,
            value=value,
        )
        fresh_reader = SQLiteTransactionConsistentFencingResourceReader(
            database, timeout_seconds=1.0
        )
        _assert_pair(
            fresh_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
            counter=counter,
            version=version,
            mutation_id=mutation_id,
            value=value,
        )

        successor_counter = counter + 1
        successor = resource.mutate(
            RESOURCE_ID,
            AUTHORITY_ID,
            successor_counter,
            mutation_id=f"mutation-{successor_counter}",
            value=f"committed-{successor_counter}",
        )
        assert successor.outcome == "applied"
        assert successor.state_changed is True

        counter = successor_counter
        version += 1
        _assert_pair(
            stale_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
            counter=counter,
            version=version,
            mutation_id=f"mutation-{counter}",
            value=f"committed-{counter}",
        )
        _assert_pair(
            fresh_reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID),
            counter=counter,
            version=version,
            mutation_id=f"mutation-{counter}",
            value=f"committed-{counter}",
        )

        # Keep the cycle count explicit: this is bounded repeated-failure evidence, not
        # a soak, reliability-rate, availability, or performance experiment.
        assert cycle < 3

    assert counter == 74
    assert version == 4


def test_repeated_parent_termination_gate_does_not_expand_truth_claims() -> None:
    assert "power-loss durability" in TRUTH_BOUNDARY
    assert "security boundary" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark" in TRUTH_BOUNDARY
    assert "novelty" in TRUTH_BOUNDARY
