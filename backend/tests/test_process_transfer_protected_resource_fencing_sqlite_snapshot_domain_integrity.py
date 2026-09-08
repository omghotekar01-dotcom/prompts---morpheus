from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from app.process_transfer_protected_resource_fencing_sqlite_snapshot import (
    SQLiteTransactionConsistentFencingResourceReader,
    TRUTH_BOUNDARY,
)


RESOURCE_ID = "resource-domain-integrity"
AUTHORITY_ID = "authority-domain-integrity"


_SCHEMA = """
CREATE TABLE morpheus_fencing_state (
    resource_id TEXT NOT NULL,
    fencing_authority_id TEXT NOT NULL,
    fencing_counter INTEGER NOT NULL,
    version INTEGER NOT NULL,
    PRIMARY KEY (resource_id, fencing_authority_id)
);
CREATE TABLE morpheus_protected_resource_state (
    resource_id TEXT NOT NULL,
    fencing_authority_id TEXT NOT NULL,
    resource_version INTEGER NOT NULL,
    value TEXT NOT NULL,
    last_mutation_id TEXT NOT NULL,
    last_fencing_counter INTEGER NOT NULL,
    PRIMARY KEY (resource_id, fencing_authority_id)
);
"""


def _create_database(
    path: Path,
    *,
    fencing_counter: object = 7,
    fencing_version: object = 3,
    resource_version: object = 3,
    value: object = "committed-value",
    mutation_id: object = "mutation-3",
    resource_counter: object = 7,
) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(_SCHEMA)
        connection.execute(
            "INSERT INTO morpheus_fencing_state(resource_id, fencing_authority_id, fencing_counter, version) VALUES (?, ?, ?, ?)",
            (RESOURCE_ID, AUTHORITY_ID, fencing_counter, fencing_version),
        )
        connection.execute(
            "INSERT INTO morpheus_protected_resource_state(resource_id, fencing_authority_id, resource_version, value, last_mutation_id, last_fencing_counter) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (RESOURCE_ID, AUTHORITY_ID, resource_version, value, mutation_id, resource_counter),
        )
        connection.commit()
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("row_values", "expected_fragment"),
    [
        ({"fencing_counter": -1, "resource_counter": -1}, "persisted fencing_counter must be a non-negative integer"),
        ({"fencing_version": 0, "resource_version": 0}, "persisted fencing version must be a positive integer"),
        ({"resource_version": 0}, "persisted resource_version must be a positive integer"),
        ({"mutation_id": "   "}, "persisted last_mutation_id must be a non-empty string"),
        ({"value": sqlite3.Binary(b"not-text")}, "persisted protected-resource value must be text"),
        ({"fencing_counter": "not-an-integer", "resource_counter": 7}, "persisted fencing_counter must be a non-negative integer"),
        ({"fencing_counter": 8, "resource_counter": 7}, "persisted fencing/resource counters disagree"),
        ({"fencing_version": 4, "resource_version": 3}, "persisted fencing/resource versions disagree"),
    ],
)
def test_snapshot_reader_rejects_schema_compatible_persisted_domain_drift_without_mutation(
    tmp_path: Path,
    row_values: dict[str, object],
    expected_fragment: str,
) -> None:
    database = tmp_path / "domain-drift.sqlite3"
    _create_database(database, **row_values)
    bytes_before = database.read_bytes()

    reader = SQLiteTransactionConsistentFencingResourceReader(database)

    with pytest.raises(ValueError, match=expected_fragment):
        reader.snapshot_pair(RESOURCE_ID, AUTHORITY_ID)

    assert database.read_bytes() == bytes_before
    assert "local SQLite" in TRUTH_BOUNDARY
    assert "does not establish" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY


def test_snapshot_reader_accepts_valid_schema_compatible_persisted_domain_state(tmp_path: Path) -> None:
    database = tmp_path / "valid-domain.sqlite3"
    _create_database(database)

    pair = SQLiteTransactionConsistentFencingResourceReader(database).snapshot_pair(
        RESOURCE_ID,
        AUTHORITY_ID,
    )

    assert pair is not None
    assert pair.fencing.fencing_counter == 7
    assert pair.fencing.version == 3
    assert pair.resource.resource_version == 3
    assert pair.resource.last_fencing_counter == 7
    assert pair.resource.last_mutation_id == "mutation-3"
    assert pair.resource.value == "committed-value"
    assert pair.automatic_control_allowed is False
    assert pair.activation_allowed is False
    assert pair.traffic_switching_allowed is False
    assert "distributed snapshot isolation" in pair.truth_boundary
    assert "power-loss durability" in pair.truth_boundary
    assert "benchmark" in pair.truth_boundary
