from __future__ import annotations

import pytest

from app.process_transfer_protected_resource_fencing_atomic import (
    AtomicFencingSnapshot,
    apply_fencing_token_with_atomic_backend,
)


class _SnapshotBackend:
    def __init__(self, snapshot: AtomicFencingSnapshot) -> None:
        self._snapshot = snapshot
        self.writes = 0

    def snapshot(self, resource_id: str, fencing_authority_id: str) -> AtomicFencingSnapshot:
        return self._snapshot

    def conditional_write(self, *args, **kwargs):
        self.writes += 1
        raise AssertionError("conditional_write must not run after an invalid snapshot")


@pytest.mark.parametrize("counter", [-1, True, 1.5])
def test_malformed_snapshot_counter_fails_closed_before_write(counter: object) -> None:
    backend = _SnapshotBackend(
        AtomicFencingSnapshot(
            resource_id="resource-a",
            fencing_authority_id="authority-a",
            fencing_counter=counter,  # type: ignore[arg-type]
            version=1,
        )
    )

    with pytest.raises(ValueError, match="snapshot fencing_counter"):
        apply_fencing_token_with_atomic_backend(backend, "resource-a", "authority-a", 2)

    assert backend.writes == 0


@pytest.mark.parametrize("version", [0, -1, True, 1.5])
def test_malformed_snapshot_version_fails_closed_before_write(version: object) -> None:
    backend = _SnapshotBackend(
        AtomicFencingSnapshot(
            resource_id="resource-a",
            fencing_authority_id="authority-a",
            fencing_counter=1,
            version=version,  # type: ignore[arg-type]
        )
    )

    with pytest.raises(ValueError, match="snapshot version"):
        apply_fencing_token_with_atomic_backend(backend, "resource-a", "authority-a", 2)

    assert backend.writes == 0


@pytest.mark.parametrize(
    ("resource_id", "authority_id"),
    [
        ("other-resource", "authority-a"),
        ("resource-a", "other-authority"),
    ],
)
def test_snapshot_identity_drift_fails_closed_before_write(resource_id: str, authority_id: str) -> None:
    backend = _SnapshotBackend(
        AtomicFencingSnapshot(
            resource_id=resource_id,
            fencing_authority_id=authority_id,
            fencing_counter=1,
            version=1,
        )
    )

    with pytest.raises(ValueError, match="snapshot identity mismatch"):
        apply_fencing_token_with_atomic_backend(backend, "resource-a", "authority-a", 2)

    assert backend.writes == 0
