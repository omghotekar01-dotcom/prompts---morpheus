from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.process_transfer_protected_resource_fencing_sqlite import SQLiteAtomicConditionalFencingBackend


TRANSACTION_ABORT_EVIDENCE_BOUNDARY = (
    "These tests inject SQLite trigger failures inside the exercised MORPHEUS local-database transaction and verify rollback and "
    "subsequent recovery for that path only. They do not establish crash consistency, power-loss durability, distributed atomicity, "
    "protected-resource enforcement, HA/SLA behavior, or production readiness."
)


def _execute(database: Path, statement: str) -> None:
    with sqlite3.connect(str(database), isolation_level=None) as connection:
        connection.execute(statement)


def test_failed_insert_transaction_rolls_back_without_partial_state_and_recovers(tmp_path: Path) -> None:
    database = tmp_path / "fencing.sqlite3"
    backend = SQLiteAtomicConditionalFencingBackend(database)

    _execute(
        database,
        """
        CREATE TRIGGER morpheus_test_abort_insert
        AFTER INSERT ON morpheus_fencing_state
        BEGIN
            SELECT RAISE(ABORT, 'injected fencing insert failure');
        END
        """,
    )

    with pytest.raises(ValueError, match="SQLite fencing conditional write failed"):
        backend.conditional_write(
            "resource-a",
            "authority-a",
            1,
            expected_version=None,
        )

    assert backend.snapshot("resource-a", "authority-a") is None

    _execute(database, "DROP TRIGGER morpheus_test_abort_insert")
    recovered = backend.conditional_write(
        "resource-a",
        "authority-a",
        1,
        expected_version=None,
    )
    assert recovered.outcome == "applied"
    assert recovered.accepted is True
    assert recovered.state_changed is True
    assert recovered.automatic_control_allowed is False
    assert recovered.activation_allowed is False
    assert recovered.traffic_switching_allowed is False

    snapshot = backend.snapshot("resource-a", "authority-a")
    assert snapshot is not None
    assert (snapshot.fencing_counter, snapshot.version) == (1, 1)


def test_failed_update_transaction_preserves_predecessor_and_retry_can_advance(tmp_path: Path) -> None:
    database = tmp_path / "fencing.sqlite3"
    backend = SQLiteAtomicConditionalFencingBackend(database)

    initial = backend.conditional_write(
        "resource-a",
        "authority-a",
        3,
        expected_version=None,
    )
    assert initial.outcome == "applied"

    _execute(
        database,
        """
        CREATE TRIGGER morpheus_test_abort_update
        AFTER UPDATE ON morpheus_fencing_state
        BEGIN
            SELECT RAISE(ABORT, 'injected fencing update failure');
        END
        """,
    )

    with pytest.raises(ValueError, match="SQLite fencing conditional write failed"):
        backend.conditional_write(
            "resource-a",
            "authority-a",
            7,
            expected_version=1,
        )

    preserved = backend.snapshot("resource-a", "authority-a")
    assert preserved is not None
    assert (preserved.fencing_counter, preserved.version) == (3, 1)

    _execute(database, "DROP TRIGGER morpheus_test_abort_update")
    recovered = backend.conditional_write(
        "resource-a",
        "authority-a",
        7,
        expected_version=1,
    )
    assert recovered.outcome == "applied"
    assert recovered.accepted is True
    assert recovered.state_changed is True
    assert recovered.automatic_control_allowed is False
    assert recovered.activation_allowed is False
    assert recovered.traffic_switching_allowed is False

    snapshot = backend.snapshot("resource-a", "authority-a")
    assert snapshot is not None
    assert (snapshot.fencing_counter, snapshot.version) == (7, 2)

    assert "verify rollback" in TRANSACTION_ABORT_EVIDENCE_BOUNDARY
    assert "do not establish crash consistency" in TRANSACTION_ABORT_EVIDENCE_BOUNDARY
    assert "production readiness" in TRANSACTION_ABORT_EVIDENCE_BOUNDARY
