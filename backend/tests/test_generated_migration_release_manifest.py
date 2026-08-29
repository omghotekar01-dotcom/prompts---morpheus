from __future__ import annotations

import pytest

from app.generated_migration_release_manifest import build_generated_migration_release_manifest


def _kwargs() -> dict[str, object]:
    return {
        "release_id": "rq7-release-v1",
        "publication_bundle_sha256": "1" * 64,
        "publication_ready": True,
        "code_commit_sha256": "2" * 64,
        "dataset_archive_sha256": "3" * 64,
        "environment_lock_sha256": "4" * 64,
        "reproducibility_command_sha256": "5" * 64,
        "supporting_artifact_sha256": ["6" * 64, "7" * 64],
        "active_revocation_count": 0,
    }


def test_release_manifest_is_order_independent() -> None:
    kwargs = _kwargs()
    first = build_generated_migration_release_manifest(**kwargs)
    kwargs["supporting_artifact_sha256"] = list(reversed(kwargs["supporting_artifact_sha256"]))  # type: ignore[arg-type]
    second = build_generated_migration_release_manifest(**kwargs)
    assert first.release_ready is True
    assert first.manifest_sha256 == second.manifest_sha256


def test_non_ready_publication_fails_closed() -> None:
    kwargs = _kwargs()
    kwargs["publication_ready"] = 1
    with pytest.raises(ValueError, match="explicitly ready"):
        build_generated_migration_release_manifest(**kwargs)


def test_active_revocation_blocks_release() -> None:
    kwargs = _kwargs()
    kwargs["active_revocation_count"] = 1
    with pytest.raises(ValueError, match="revoked"):
        build_generated_migration_release_manifest(**kwargs)


def test_boolean_revocation_count_alias_fails_closed() -> None:
    kwargs = _kwargs()
    kwargs["active_revocation_count"] = False
    with pytest.raises(ValueError, match="exact integer"):
        build_generated_migration_release_manifest(**kwargs)


def test_required_identity_aliasing_is_rejected() -> None:
    kwargs = _kwargs()
    kwargs["dataset_archive_sha256"] = "2" * 64
    with pytest.raises(ValueError, match="independent"):
        build_generated_migration_release_manifest(**kwargs)


def test_supporting_identity_aliasing_is_rejected() -> None:
    kwargs = _kwargs()
    kwargs["supporting_artifact_sha256"] = ["1" * 64]
    with pytest.raises(ValueError, match="independent"):
        build_generated_migration_release_manifest(**kwargs)
