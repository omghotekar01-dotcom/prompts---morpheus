from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.process_transfer_protected_resource_fencing_atomic import apply_fencing_token_with_atomic_backend
from app.process_transfer_protected_resource_fencing_sqlite import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    SQLiteAtomicConditionalFencingBackend,
)


def _backend(tmp_path: Path) -> SQLiteAtomicConditionalFencingBackend:
    return SQLiteAtomicConditionalFencingBackend(tmp_path / "fencing.sqlite3")


def test_sqlite_backend_preserves_first_newer_equal_and_stale_semantics(tmp_path: Path) -> None:
    backend = _backend(tmp_path)

    first = apply_fencing_token_with_atomic_backend(backend, "resource-a", "authority-a", 4)
    newer = apply_fencing_token_with_atomic_backend(backend, "resource-a", "authority-a", 7)
    equal = apply_fencing_token_with_atomic_backend(backend, "resource-a", "authority-a", 7)
    stale = apply_fencing_token_with_atomic_backend(backend, "resource-a", "authority-a", 6)

    assert (first.outcome, first.observed_version) == ("applied", 1)
    assert (newer.outcome, newer.observed_version) == ("applied", 2)
    assert equal.outcome == "idempotent"
    assert equal.accepted is True and equal.state_changed is False
    assert stale.outcome == "stale"
    assert stale.accepted is False and stale.state_changed is False
    assert backend.snapshot("resource-a", "authority-a").fencing_counter == 7  # type: ignore[union-attr]


def test_sqlite_backend_state_survives_backend_reconstruction(tmp_path: Path) -> None:
    database = tmp_path / "fencing.sqlite3"
    original = SQLiteAtomicConditionalFencingBackend(database)
    assert apply_fencing_token_with_atomic_backend(original, "resource-a", "authority-a", 11).outcome == "applied"

    reconstructed = SQLiteAtomicConditionalFencingBackend(database)
    snapshot = reconstructed.snapshot("resource-a", "authority-a")

    assert snapshot is not None
    assert (snapshot.fencing_counter, snapshot.version) == (11, 1)
    assert apply_fencing_token_with_atomic_backend(reconstructed, "resource-a", "authority-a", 12).outcome == "applied"
    assert reconstructed.snapshot("resource-a", "authority-a").version == 2  # type: ignore[union-attr]


def test_relative_database_path_is_pinned_across_working_directory_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original_directory = tmp_path / "original"
    moved_directory = tmp_path / "moved"
    original_directory.mkdir()
    moved_directory.mkdir()
    monkeypatch.chdir(original_directory)

    backend = SQLiteAtomicConditionalFencingBackend(Path("fencing.sqlite3"))
    assert backend.database_path == (original_directory / "fencing.sqlite3").resolve()
    assert apply_fencing_token_with_atomic_backend(backend, "resource-a", "authority-a", 3).outcome == "applied"

    monkeypatch.chdir(moved_directory)
    snapshot = backend.snapshot("resource-a", "authority-a")
    assert snapshot is not None
    assert (snapshot.fencing_counter, snapshot.version) == (3, 1)
    assert apply_fencing_token_with_atomic_backend(backend, "resource-a", "authority-a", 4).outcome == "applied"
    assert not (moved_directory / "fencing.sqlite3").exists()

    reconstructed = SQLiteAtomicConditionalFencingBackend(original_directory / "fencing.sqlite3")
    reconstructed_snapshot = reconstructed.snapshot("resource-a", "authority-a")
    assert reconstructed_snapshot is not None
    assert (reconstructed_snapshot.fencing_counter, reconstructed_snapshot.version) == (4, 2)


def test_independent_connections_detect_moved_predecessor_version(tmp_path: Path) -> None:
    database = tmp_path / "fencing.sqlite3"
    first = SQLiteAtomicConditionalFencingBackend(database)
    second = SQLiteAtomicConditionalFencingBackend(database)
    assert apply_fencing_token_with_atomic_backend(first, "resource-a", "authority-a", 1).outcome == "applied"

    predecessor = first.snapshot("resource-a", "authority-a")
    assert predecessor is not None and predecessor.version == 1
    assert second.conditional_write("resource-a", "authority-a", 2, expected_version=1).outcome == "applied"

    conflict = first.conditional_write("resource-a", "authority-a", 3, expected_version=predecessor.version)
    assert conflict.outcome == "conflict"
    assert conflict.accepted is False and conflict.state_changed is False
    snapshot = first.snapshot("resource-a", "authority-a")
    assert snapshot is not None
    assert (snapshot.fencing_counter, snapshot.version) == (2, 2)


def test_sqlite_backend_isolates_resource_and_authority_identity(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    assert apply_fencing_token_with_atomic_backend(backend, "resource-a", "authority-a", 9).outcome == "applied"
    assert apply_fencing_token_with_atomic_backend(backend, "resource-b", "authority-a", 2).outcome == "applied"
    assert apply_fencing_token_with_atomic_backend(backend, "resource-a", "authority-b", 5).outcome == "applied"

    assert backend.snapshot("resource-a", "authority-a").fencing_counter == 9  # type: ignore[union-attr]
    assert backend.snapshot("resource-b", "authority-a").fencing_counter == 2  # type: ignore[union-attr]
    assert backend.snapshot("resource-a", "authority-b").fencing_counter == 5  # type: ignore[union-attr]


def test_competing_independent_connections_do_not_both_apply_same_predecessor(tmp_path: Path) -> None:
    database = tmp_path / "fencing.sqlite3"
    seed = SQLiteAtomicConditionalFencingBackend(database)
    assert seed.conditional_write("resource-a", "authority-a", 1, expected_version=None).outcome == "applied"

    def write(counter: int) -> str:
        backend = SQLiteAtomicConditionalFencingBackend(database)
        return backend.conditional_write("resource-a", "authority-a", counter, expected_version=1).outcome

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(write, (2, 3)))

    assert outcomes.count("applied") == 1
    assert set(outcomes) <= {"applied", "conflict", "stale"}
    snapshot = seed.snapshot("resource-a", "authority-a")
    assert snapshot is not None
    assert snapshot.version == 2
    assert snapshot.fencing_counter in {2, 3}


def test_sqlite_backend_rejects_invalid_inputs_before_state_transition(tmp_path: Path) -> None:
    backend = _backend(tmp_path)

    with pytest.raises(ValueError, match="resource_id"):
        backend.conditional_write("", "authority-a", 1, expected_version=None)
    with pytest.raises(ValueError, match="fencing_counter"):
        backend.conditional_write("resource-a", "authority-a", True, expected_version=None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="expected_version"):
        backend.conditional_write("resource-a", "authority-a", 1, expected_version=0)

    assert backend.snapshot("resource-a", "authority-a") is None


def test_sqlite_backend_requires_existing_parent_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="parent directory"):
        SQLiteAtomicConditionalFencingBackend(tmp_path / "missing" / "fencing.sqlite3")


def test_sqlite_backend_keeps_truth_and_authority_boundaries_explicit(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    result = apply_fencing_token_with_atomic_backend(backend, "resource-a", "authority-a", 1)

    assert result.evidence_state == EVIDENCE_STATE
    assert result.automatic_control_allowed is False
    assert result.activation_allowed is False
    assert result.traffic_switching_allowed is False
    assert "SQLite" in TRUTH_BOUNDARY
    assert "does not establish distributed linearizability" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
