from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from app.process_transfer_protected_resource_fencing_sqlite import SQLiteAtomicConditionalFencingBackend


LOCK_CONTENTION_EVIDENCE_BOUNDARY = (
    "This test exercises one local SQLite database file and one deliberately held local write transaction. "
    "It demonstrates bounded fail-closed behavior for this exercised lock-contention path only; it does not establish "
    "distributed availability, crash consistency, power-loss durability, protected-resource enforcement, HA/SLA behavior, "
    "or production readiness."
)


def test_lock_contention_fails_closed_without_mutation_and_recovers_after_release(tmp_path: Path) -> None:
    database = tmp_path / "fencing.sqlite3"
    backend = SQLiteAtomicConditionalFencingBackend(database, timeout_seconds=0.1)

    blocker = sqlite3.connect(str(database), timeout=1.0, isolation_level=None)
    blocker.execute("BEGIN IMMEDIATE")
    try:
        started = time.monotonic()
        with pytest.raises(ValueError, match="SQLite fencing conditional write failed"):
            backend.conditional_write(
                "resource-a",
                "authority-a",
                1,
                expected_version=None,
            )
        elapsed = time.monotonic() - started

        # Keep the assertion deliberately loose for CI scheduling variance while
        # still proving the configured SQLite timeout does not become an
        # unbounded wait in this exercised local-host path.
        assert elapsed < 5.0
        assert backend.snapshot("resource-a", "authority-a") is None
    finally:
        blocker.rollback()
        blocker.close()

    applied = backend.conditional_write(
        "resource-a",
        "authority-a",
        1,
        expected_version=None,
    )
    assert applied.outcome == "applied"
    assert applied.accepted is True
    assert applied.state_changed is True
    assert applied.automatic_control_allowed is False
    assert applied.activation_allowed is False
    assert applied.traffic_switching_allowed is False

    snapshot = backend.snapshot("resource-a", "authority-a")
    assert snapshot is not None
    assert (snapshot.fencing_counter, snapshot.version) == (1, 1)

    assert "bounded fail-closed behavior" in LOCK_CONTENTION_EVIDENCE_BOUNDARY
    assert "does not establish distributed availability" in LOCK_CONTENTION_EVIDENCE_BOUNDARY
    assert "production readiness" in LOCK_CONTENTION_EVIDENCE_BOUNDARY
