from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from app.process_transfer_protected_resource_fencing_sqlite_snapshot import (
    SQLiteTransactionConsistentFencingResourceReader,
    TRUTH_BOUNDARY,
)


def _create_shape_database(
    database: Path,
    *,
    fencing_primary_key: str = "resource_id, fencing_authority_id",
    resource_primary_key: str = "resource_id, fencing_authority_id",
    fencing_counter_not_null: bool = True,
    last_mutation_id_not_null: bool = True,
    fencing_counter_type: str = "INTEGER",
    resource_value_type: str = "TEXT",
) -> None:
    fencing_counter_constraint = " NOT NULL" if fencing_counter_not_null else ""
    mutation_constraint = " NOT NULL" if last_mutation_id_not_null else ""
    with sqlite3.connect(database) as connection:
        connection.execute(
            f"""
            CREATE TABLE morpheus_fencing_state (
                resource_id TEXT NOT NULL,
                fencing_authority_id TEXT NOT NULL,
                fencing_counter {fencing_counter_type}{fencing_counter_constraint},
                version INTEGER NOT NULL,
                PRIMARY KEY ({fencing_primary_key})
            )
            """
        )
        connection.execute(
            f"""
            CREATE TABLE morpheus_protected_resource_state (
                resource_id TEXT NOT NULL,
                fencing_authority_id TEXT NOT NULL,
                resource_version INTEGER NOT NULL,
                value {resource_value_type} NOT NULL,
                last_mutation_id TEXT{mutation_constraint},
                last_fencing_counter INTEGER NOT NULL,
                PRIMARY KEY ({resource_primary_key})
            )
            """
        )
        connection.execute("CREATE TABLE unrelated_preserved(marker TEXT NOT NULL)")
        connection.execute("INSERT INTO unrelated_preserved(marker) VALUES ('untouched')")


@pytest.mark.parametrize(
    ("kwargs", "expected_fragment"),
    [
        (
            {"fencing_primary_key": "fencing_authority_id, resource_id"},
            "morpheus_fencing_state(primary key must be resource_id, fencing_authority_id)",
        ),
        (
            {"resource_primary_key": "resource_id"},
            "morpheus_protected_resource_state(primary key must be resource_id, fencing_authority_id)",
        ),
        (
            {"fencing_counter_not_null": False},
            "morpheus_fencing_state(required columns must be NOT NULL: fencing_counter)",
        ),
        (
            {"last_mutation_id_not_null": False},
            "morpheus_protected_resource_state(required columns must be NOT NULL: last_mutation_id)",
        ),
        (
            {"fencing_counter_type": "TEXT"},
            "morpheus_fencing_state(required columns have incompatible declared types: fencing_counter)",
        ),
        (
            {"resource_value_type": "BLOB"},
            "morpheus_protected_resource_state(required columns have incompatible declared types: value)",
        ),
    ],
)
def test_reader_constructor_rejects_incompatible_required_shape_without_mutation(
    tmp_path: Path,
    kwargs: dict[str, object],
    expected_fragment: str,
) -> None:
    database = tmp_path / "shape-drift.sqlite3"
    _create_shape_database(database, **kwargs)

    before_bytes = database.read_bytes()
    with pytest.raises(ValueError, match="incompatible required schema") as exc_info:
        SQLiteTransactionConsistentFencingResourceReader(database)

    assert expected_fragment in str(exc_info.value)
    assert database.read_bytes() == before_bytes
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT marker FROM unrelated_preserved"
        ).fetchall() == [("untouched",)]


def test_schema_shape_gate_keeps_production_and_scientific_claims_bounded() -> None:
    boundary = TRUTH_BOUNDARY.lower()
    assert "local sqlite" in boundary
    assert "production readiness" in boundary
    assert "benchmark" in boundary
    assert "novelty" in boundary
    assert "patentability" in boundary
    assert "scientific-effect claim" in boundary
