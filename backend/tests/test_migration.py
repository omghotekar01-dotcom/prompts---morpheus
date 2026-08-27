from __future__ import annotations

import pytest

from app.migration import MigrationController


ARTIFACT = "a" * 64
MANIFEST = "b" * 64


def test_migration_requires_shadow_build_and_both_verification_gates_before_commit() -> None:
    controller = MigrationController()
    planned = controller.plan(
        "migration-1",
        session_id="session-1",
        from_candidate_id="candidate-old",
        to_candidate_id="candidate-new",
    )
    assert planned["state"] == "PLANNED"

    with pytest.raises(ValueError, match="VERIFIED"):
        controller.commit("migration-1")

    built = controller.shadow_built("migration-1", artifact_sha256=ARTIFACT)
    assert built["state"] == "SHADOW_BUILT"

    failed_verification = controller.verify(
        "migration-1",
        compile_verified=True,
        correctness_verified=False,
        verification_manifest_sha256=MANIFEST,
    )
    assert failed_verification["state"] == "SHADOW_BUILT"

    with pytest.raises(ValueError, match="VERIFIED"):
        controller.commit("migration-1")


def test_migration_commit_and_rollback_preserve_previous_candidate() -> None:
    controller = MigrationController()
    controller.plan(
        "migration-2",
        session_id="session-1",
        from_candidate_id="candidate-old",
        to_candidate_id="candidate-new",
    )
    controller.shadow_built("migration-2", artifact_sha256=ARTIFACT)
    verified = controller.verify(
        "migration-2",
        compile_verified=True,
        correctness_verified=True,
        verification_manifest_sha256=MANIFEST,
    )
    assert verified["state"] == "VERIFIED"

    committed = controller.commit("migration-2")
    assert committed["state"] == "COMMITTED"
    assert committed["rollback_candidate_id"] == "candidate-old"
    assert committed["evidence_state"] == "MIGRATION_CONTROL_PLANE_ONLY_NO_LIVE_PROCESS_SWAP"

    rolled_back = controller.rollback("migration-2", reason="post-commit health gate failed")
    assert rolled_back["state"] == "ROLLED_BACK"
    assert rolled_back["history"][-1]["restore_candidate_id"] == "candidate-old"


def test_migration_can_abort_before_commit_but_not_after_commit() -> None:
    controller = MigrationController()
    controller.plan(
        "migration-abort",
        session_id="session-2",
        from_candidate_id="a",
        to_candidate_id="b",
    )
    aborted = controller.abort("migration-abort", reason="artifact generation failed")
    assert aborted["state"] == "ABORTED"

    controller.plan(
        "migration-commit",
        session_id="session-2",
        from_candidate_id="a",
        to_candidate_id="b",
    )
    controller.shadow_built("migration-commit", artifact_sha256=ARTIFACT)
    controller.verify(
        "migration-commit",
        compile_verified=True,
        correctness_verified=True,
        verification_manifest_sha256=MANIFEST,
    )
    controller.commit("migration-commit")
    with pytest.raises(ValueError, match="cannot abort"):
        controller.abort("migration-commit", reason="too late")
