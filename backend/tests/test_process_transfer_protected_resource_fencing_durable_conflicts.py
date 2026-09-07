from __future__ import annotations

from pathlib import Path

import pytest

from app.process_transfer_protected_resource_fencing_durable import (
    DurableFencingStateConflict,
    DurableProtectedResourceFencingModel,
    TRUTH_BOUNDARY,
)


def test_noncooperating_change_after_verified_read_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state_path = tmp_path / "fencing-state.json"
    seed = DurableProtectedResourceFencingModel(state_path, "resource-a", "fence-a")
    assert seed.validate_fencing_token("resource-a", "fence-a", 9).accepted is True

    first = DurableProtectedResourceFencingModel(state_path, "resource-a", "fence-a")
    original_stage = first._stage_candidate

    def stage_then_external_advance(expected: bytes) -> Path:
        staged = original_stage(expected)
        # Deliberately bypass the MORPHEUS sidecar lock to model a non-cooperating
        # local writer. The pre-replacement byte check must still fail closed.
        state_path.write_bytes(first._canonical_bytes(11))
        return staged

    monkeypatch.setattr(first, "_stage_candidate", stage_then_external_advance)

    with pytest.raises(DurableFencingStateConflict, match="changed after verified read"):
        first.validate_fencing_token("resource-a", "fence-a", 10)

    recovered = DurableProtectedResourceFencingModel(state_path, "resource-a", "fence-a")
    assert recovered.snapshot() is not None
    assert recovered.snapshot().highest_accepted_fencing_counter == 11
    assert list(tmp_path.glob(".fencing-state.json.*.tmp")) == []


def test_noncooperating_deletion_after_verified_read_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state_path = tmp_path / "fencing-state.json"
    seed = DurableProtectedResourceFencingModel(state_path, "resource-a", "fence-a")
    assert seed.validate_fencing_token("resource-a", "fence-a", 9).accepted is True

    first = DurableProtectedResourceFencingModel(state_path, "resource-a", "fence-a")
    original_stage = first._stage_candidate

    def stage_then_external_delete(expected: bytes) -> Path:
        staged = original_stage(expected)
        # Deliberately bypass the MORPHEUS sidecar lock and delete the live state.
        # The verified previous bytes must not be silently replaced with a new state.
        state_path.unlink()
        return staged

    monkeypatch.setattr(first, "_stage_candidate", stage_then_external_delete)

    with pytest.raises(DurableFencingStateConflict, match="changed after verified read"):
        first.validate_fencing_token("resource-a", "fence-a", 10)

    assert state_path.exists() is False
    assert list(tmp_path.glob(".fencing-state.json.*.tmp")) == []


def test_noncooperating_creation_after_absent_read_is_detected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state_path = tmp_path / "fencing-state.json"
    first = DurableProtectedResourceFencingModel(state_path, "resource-a", "fence-a")
    original_stage = first._stage_candidate

    def stage_then_external_create(expected: bytes) -> Path:
        staged = original_stage(expected)
        # This direct write intentionally does not acquire the cooperative host lock.
        state_path.write_bytes(first._canonical_bytes(2))
        return staged

    monkeypatch.setattr(first, "_stage_candidate", stage_then_external_create)

    with pytest.raises(DurableFencingStateConflict, match="changed after verified read"):
        first.validate_fencing_token("resource-a", "fence-a", 1)

    recovered = DurableProtectedResourceFencingModel(state_path, "resource-a", "fence-a")
    assert recovered.snapshot() is not None
    assert recovered.snapshot().highest_accepted_fencing_counter == 2
    assert list(tmp_path.glob(".fencing-state.json.*.tmp")) == []


def test_independent_cooperating_adapters_preserve_stale_equal_new_semantics(tmp_path: Path) -> None:
    state_path = tmp_path / "fencing-state.json"
    first = DurableProtectedResourceFencingModel(state_path, "resource-a", "fence-a")
    assert first.validate_fencing_token("resource-a", "fence-a", 4).accepted is True

    second = DurableProtectedResourceFencingModel(state_path, "resource-a", "fence-a")
    assert second.validate_fencing_token("resource-a", "fence-a", 4).accepted is True
    assert second.validate_fencing_token("resource-a", "fence-a", 3).accepted is False
    assert second.validate_fencing_token("resource-a", "fence-a", 6).accepted is True

    assert first.validate_fencing_token("resource-a", "fence-a", 5).accepted is False
    assert first.validate_fencing_token("resource-a", "fence-a", 6).accepted is True
    assert first.snapshot() is not None
    assert first.snapshot().highest_accepted_fencing_counter == 6


def test_conflict_gate_never_escalates_runtime_authority(tmp_path: Path) -> None:
    model = DurableProtectedResourceFencingModel(tmp_path / "fencing-state.json", "resource-a", "fence-a")

    assert model.automatic_control_allowed is False
    assert model.activation_allowed is False
    assert model.traffic_switching_allowed is False


def test_truth_boundary_denies_noncooperating_distributed_and_scientific_claims() -> None:
    boundary = TRUTH_BOUNDARY.lower()

    assert "advisory" in boundary
    assert "non-cooperating process or external writer" in boundary
    assert "does not establish distributed locking or linearizability" in boundary
    assert "power-loss durability" in boundary
    assert "no benchmark" in boundary
    assert "production-readiness claim" in boundary
