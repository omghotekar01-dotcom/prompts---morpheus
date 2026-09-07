from __future__ import annotations

from pathlib import Path

import pytest

from app.process_transfer_protected_resource_fencing_durable import DurableProtectedResourceFencingModel


@pytest.mark.parametrize("version_json", ["true", "1.0", '"1"', "null"])
def test_persisted_version_requires_exact_integer_schema_type(tmp_path: Path, version_json: str) -> None:
    state_path = tmp_path / "fencing-state.json"
    state_path.write_text(
        '{"fencing_authority_id":"fence-a","highest_accepted_fencing_counter":9,'
        f'"resource_id":"resource-a","version":{version_json}}}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="version mismatch"):
        DurableProtectedResourceFencingModel(state_path, "resource-a", "fence-a")


def test_persisted_counter_rejects_boolean_even_when_json_number_equivalent(tmp_path: Path) -> None:
    state_path = tmp_path / "fencing-state.json"
    state_path.write_text(
        '{"fencing_authority_id":"fence-a","highest_accepted_fencing_counter":true,'
        '"resource_id":"resource-a","version":1}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="fencing_counter"):
        DurableProtectedResourceFencingModel(state_path, "resource-a", "fence-a")
