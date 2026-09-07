from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3

import pytest

from app.process_transfer_protected_resource_fencing_sqlite import SQLiteAtomicConditionalFencingBackend
from app.process_transfer_protected_resource_fencing_sqlite_resource import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    SQLiteTransactionallyFencedProtectedResource,
)


def _resource(tmp_path: Path) -> SQLiteTransactionallyFencedProtectedResource:
    return SQLiteTransactionallyFencedProtectedResource(tmp_path / "fencing.sqlite3")


def test_first_newer_equal_and_stale_resource_mutations_are_fencing_bound(tmp_path: Path) -> None:
    resource = _resource(tmp_path)

    first = resource.mutate("resource-a", "authority-a", 3, mutation_id="m-1", value="alpha")
    newer = resource.mutate("resource-a", "authority-a", 5, mutation_id="m-2", value="beta")
    equal = resource.mutate("resource-a", "authority-a", 5, mutation_id="m-2", value="beta")
    stale = resource.mutate("resource-a", "authority-a", 4, mutation_id="m-3", value="gamma")

    assert (first.outcome, first.fencing_version, first.resource_version) == ("applied", 1, 1)
    assert (newer.outcome, newer.fencing_version, newer.resource_version) == ("applied", 2, 2)
    assert equal.outcome == "idempotent"
    assert equal.accepted is True and equal.state_changed is False
    assert stale.outcome == "stale"
    assert stale.accepted is False and stale.state_changed is False
    snapshot = resource.snapshot("resource-a", "authority-a")
    assert snapshot is not None
    assert (snapshot.value, snapshot.resource_version, snapshot.last_fencing_counter) == ("beta", 2, 5)


def test_equal_generation_cannot_be_reused_for_a_different_mutation(tmp_path: Path) -> None:
    resource = _resource(tmp_path)
    assert resource.mutate("resource-a", "authority-a", 7, mutation_id="m-1", value="alpha").outcome == "applied"

    reused_id = resource.mutate("resource-a", "authority-a", 7, mutation_id="m-2", value="alpha")
    reused_value = resource.mutate("resource-a", "authority-a", 7, mutation_id="m-1", value="beta")

    assert reused_id.outcome == "generation_reuse_rejected"
    assert reused_value.outcome == "generation_reuse_rejected"
    assert reused_id.accepted is False and reused_value.accepted is False
    snapshot = resource.snapshot("resource-a", "authority-a")
    assert snapshot is not None
    assert (snapshot.value, snapshot.last_mutation_id, snapshot.resource_version) == ("alpha", "m-1", 1)


def test_resource_and_authority_identities_are_isolated(tmp_path: Path) -> None:
    resource = _resource(tmp_path)
    assert resource.mutate("resource-a", "authority-a", 2, mutation_id="aa", value="A/A").outcome == "applied"
    assert resource.mutate("resource-b", "authority-a", 1, mutation_id="ba", value="B/A").outcome == "applied"
    assert resource.mutate("resource-a", "authority-b", 4, mutation_id="ab", value="A/B").outcome == "applied"

    assert resource.snapshot("resource-a", "authority-a").value == "A/A"  # type: ignore[union-attr]
    assert resource.snapshot("resource-b", "authority-a").value == "B/A"  # type: ignore[union-attr]
    assert resource.snapshot("resource-a", "authority-b").value == "A/B"  # type: ignore[union-attr]


def test_injected_resource_mutation_failure_rolls_back_fencing_and_resource_state(tmp_path: Path) -> None:
    database = tmp_path / "fencing.sqlite3"
    resource = SQLiteTransactionallyFencedProtectedResource(database)
    fencing = SQLiteAtomicConditionalFencingBackend(database)
    assert resource.mutate("resource-a", "authority-a", 1, mutation_id="m-1", value="alpha").outcome == "applied"

    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TRIGGER fail_resource_update BEFORE UPDATE ON morpheus_protected_resource_state "
            "BEGIN SELECT RAISE(ABORT, 'injected resource mutation failure'); END"
        )

    with pytest.raises(ValueError, match="transactionally fenced protected-resource mutation failed"):
        resource.mutate("resource-a", "authority-a", 2, mutation_id="m-2", value="beta")

    fencing_snapshot = fencing.snapshot("resource-a", "authority-a")
    resource_snapshot = resource.snapshot("resource-a", "authority-a")
    assert fencing_snapshot is not None and resource_snapshot is not None
    assert (fencing_snapshot.fencing_counter, fencing_snapshot.version) == (1, 1)
    assert (resource_snapshot.value, resource_snapshot.resource_version, resource_snapshot.last_fencing_counter) == ("alpha", 1, 1)

    with sqlite3.connect(database) as connection:
        connection.execute("DROP TRIGGER fail_resource_update")

    recovered = resource.mutate("resource-a", "authority-a", 2, mutation_id="m-2", value="beta")
    assert (recovered.outcome, recovered.fencing_version, recovered.resource_version) == ("applied", 2, 2)


def test_injected_first_resource_insert_failure_leaves_no_fencing_authority(tmp_path: Path) -> None:
    database = tmp_path / "fencing.sqlite3"
    resource = SQLiteTransactionallyFencedProtectedResource(database)
    fencing = SQLiteAtomicConditionalFencingBackend(database)

    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TRIGGER fail_resource_insert BEFORE INSERT ON morpheus_protected_resource_state "
            "BEGIN SELECT RAISE(ABORT, 'injected resource insert failure'); END"
        )

    with pytest.raises(ValueError, match="transactionally fenced protected-resource mutation failed"):
        resource.mutate("resource-a", "authority-a", 1, mutation_id="m-1", value="alpha")

    assert resource.snapshot("resource-a", "authority-a") is None
    assert fencing.snapshot("resource-a", "authority-a") is None


def test_competing_same_generation_writers_commit_only_one_distinct_mutation(tmp_path: Path) -> None:
    database = tmp_path / "fencing.sqlite3"
    seed = SQLiteTransactionallyFencedProtectedResource(database)
    assert seed.mutate("resource-a", "authority-a", 1, mutation_id="seed", value="seed").outcome == "applied"

    def write(mutation: tuple[str, str]) -> tuple[str, str, str]:
        mutation_id, value = mutation
        local = SQLiteTransactionallyFencedProtectedResource(database)
        result = local.mutate("resource-a", "authority-a", 2, mutation_id=mutation_id, value=value)
        return mutation_id, value, result.outcome

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(write, (("m-a", "alpha"), ("m-b", "beta"))))

    assert [outcome for _, _, outcome in results].count("applied") == 1
    assert [outcome for _, _, outcome in results].count("generation_reuse_rejected") == 1
    winner = next((mutation_id, value) for mutation_id, value, outcome in results if outcome == "applied")
    snapshot = seed.snapshot("resource-a", "authority-a")
    assert snapshot is not None
    assert (snapshot.last_mutation_id, snapshot.value, snapshot.last_fencing_counter, snapshot.resource_version) == (
        winner[0], winner[1], 2, 2
    )


def test_invalid_inputs_fail_before_resource_state_is_created(tmp_path: Path) -> None:
    resource = _resource(tmp_path)
    with pytest.raises(ValueError, match="resource_id"):
        resource.mutate("", "authority-a", 1, mutation_id="m-1", value="alpha")
    with pytest.raises(ValueError, match="fencing_counter"):
        resource.mutate("resource-a", "authority-a", True, mutation_id="m-1", value="alpha")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="mutation_id"):
        resource.mutate("resource-a", "authority-a", 1, mutation_id="", value="alpha")
    with pytest.raises(ValueError, match="value"):
        resource.mutate("resource-a", "authority-a", 1, mutation_id="m-1", value=1)  # type: ignore[arg-type]
    assert resource.snapshot("resource-a", "authority-a") is None


def test_truth_and_production_authority_boundaries_remain_explicit(tmp_path: Path) -> None:
    result = _resource(tmp_path).mutate("resource-a", "authority-a", 1, mutation_id="m-1", value="alpha")

    assert result.evidence_state == EVIDENCE_STATE
    assert result.automatic_control_allowed is False
    assert result.activation_allowed is False
    assert result.traffic_switching_allowed is False
    assert "same SQLite transaction" in TRUTH_BOUNDARY
    assert "does not establish atomicity or fencing enforcement for arbitrary external resources" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
