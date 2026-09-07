from __future__ import annotations

from pathlib import Path

import pytest

from app.process_transfer_protected_resource_fencing_durable import DurableProtectedResourceFencingModel


def test_live_adapter_fails_closed_if_established_state_disappears(tmp_path: Path) -> None:
    state_path = tmp_path / "fencing-state.json"
    model = DurableProtectedResourceFencingModel(state_path, "resource-a", "fence-a")

    assert model.validate_fencing_token("resource-a", "fence-a", 9).accepted is True
    state_path.unlink()

    with pytest.raises(ValueError, match="state disappeared after being established"):
        model.snapshot()
    with pytest.raises(ValueError, match="state disappeared after being established"):
        model.validate_fencing_token("resource-a", "fence-a", 1)

    assert not state_path.exists()


def test_fresh_adapter_still_allows_a_genuinely_absent_store(tmp_path: Path) -> None:
    state_path = tmp_path / "fencing-state.json"
    model = DurableProtectedResourceFencingModel(state_path, "resource-a", "fence-a")

    assert model.snapshot() is None
    assert model.validate_fencing_token("resource-a", "fence-a", 1).accepted is True
    assert state_path.is_file()
