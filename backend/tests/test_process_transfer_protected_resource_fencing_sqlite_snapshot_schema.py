from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from app.process_transfer_protected_resource_fencing_sqlite_resource import (
    SQLiteTransactionallyFencedProtectedResource,
)
from app.process_transfer_protected_resource_fencing_sqlite_snapshot import (
    SQLiteTransactionConsistentFencingResourceReader,
)


def _create_schema_drift_database(database: Path, *, drift_table: str) -> None:
    with sqlite3.connect(database) as connection:
        if drift_table == "morpheus_fencing_state":
            connection.execute(
                """
                CREATE TABLE morpheus_fencing_state (
                    resource_id TEXT NOT NULL,
                    fencing_authority_id TEXT NOT NULL,
                    fencing_counter INTEGER NOT NULL,
                    PRIMARY KEY (resource_id, fencing_authority_id)
                )
                """
            )
        else:
            connection.execute(
                """
                CREATE TABLE morpheus_fencing_state (
                    resource_id TEXT NOT NULL,
                    fencing_authority_id TEXT NOT NULL,
                    fencing_counter INTEGER NOT NULL,
                    version INTEGER NOT NULL,
                    PRIMARY KEY (resource_id, fencing_authority_id)
                )
                """
            )

        if drift_table == "morpheus_protected_resource_state":
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
        else:
            connection.execute(
                """
                CREATE TABLE morpheus_protected_resource_state (
                    resource_id TEXT NOT NULL,
                    fencing_authority_id TEXT NOT NULL,
                    resource_version INTEGER NOT NULL,
                    value TEXT NOT NULL,
                    last_mutation_id TEXT NOT NULL,
                    last_fencing_counter INTEGER NOT NULL,
                    PRIMARY KEY (resource_id, fencing_authority_id)
                )
                """
            )
        connection.execute("CREATE TABLE unrelated_preserved(marker TEXT NOT NULL)")
        connection.execute("INSERT INTO unrelated_preserved(marker) VALUES ('untouched')")


@pytest.mark.parametrize(
    ("drift_table", "missing_column"),
    [
        ("morpheus_fencing_state", "version"),
        ("morpheus_protected_resource_state", "last_mutation_id"),
    ],
)
def test_reader_constructor_fails_closed_for_required_column_drift_without_mutation(
    tmp_path: Path,
    drift_table: str,
    missing_column: str,
) -> None:
    database = tmp_path / "drifted.sqlite3"
    _create_schema_drift_database(database, drift_table=drift_table)

    before_bytes = database.read_bytes()
    with pytest.raises(
        ValueError,
        match=rf"missing required columns: .*{drift_table}.*{missing_column}",
    ):
        SQLiteTransactionConsistentFencingResourceReader(database)

    assert database.read_bytes() == before_bytes
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT marker FROM unrelated_preserved"
        ).fetchall() == [("untouched",)]


def test_reader_constructor_accepts_current_schema_contract_and_observes_pair(
    tmp_path: Path,
) -> None:
    database = tmp_path / "current.sqlite3"
    resource = SQLiteTransactionallyFencedProtectedResource(database)
    result = resource.mutate(
        "resource-a",
        "authority-a",
        1,
        mutation_id="m-1",
        value="v-1",
    )
    assert result.outcome == "applied"

    reader = SQLiteTransactionConsistentFencingResourceReader(database)
    pair = reader.snapshot_pair("resource-a", "authority-a")

    assert pair is not None
    assert pair.fencing.fencing_counter == 1
    assert pair.fencing.version == 1
    assert pair.resource.resource_version == 1
    assert pair.resource.last_fencing_counter == 1
    assert pair.resource.last_mutation_id == "m-1"
    assert pair.resource.value == "v-1"
    assert pair.automatic_control_allowed is False
    assert pair.activation_allowed is False
    assert pair.traffic_switching_allowed is False
