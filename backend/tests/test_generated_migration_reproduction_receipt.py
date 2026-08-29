from __future__ import annotations

import pytest

from app.generated_migration_reproduction_receipt import build_generated_migration_reproduction_receipt


def _kwargs() -> dict[str, object]:
    return {
        "run_id": "rq7-repro-001",
        "release_manifest_sha256": "1" * 64,
        "release_ready": True,
        "runner_environment_sha256": "2" * 64,
        "stdout_artifact_sha256": "3" * 64,
        "result_artifact_sha256": "4" * 64,
        "exit_code": 0,
        "assertions_passed": 12,
    }


def test_verified_reproduction_is_content_addressed() -> None:
    first = build_generated_migration_reproduction_receipt(**_kwargs())
    second = build_generated_migration_reproduction_receipt(**_kwargs())
    assert first.reproduction_verified is True
    assert first.receipt_sha256 == second.receipt_sha256


def test_nonzero_exit_fails_closed() -> None:
    values = _kwargs(); values["exit_code"] = 1
    with pytest.raises(ValueError, match="exit successfully"):
        build_generated_migration_reproduction_receipt(**values)


def test_boolean_exit_alias_fails_closed() -> None:
    values = _kwargs(); values["exit_code"] = False
    with pytest.raises(ValueError, match="exact integer"):
        build_generated_migration_reproduction_receipt(**values)


def test_zero_assertions_fail_closed() -> None:
    values = _kwargs(); values["assertions_passed"] = 0
    with pytest.raises(ValueError, match="positive exact integer"):
        build_generated_migration_reproduction_receipt(**values)


def test_identity_aliasing_is_rejected() -> None:
    values = _kwargs(); values["result_artifact_sha256"] = "3" * 64
    with pytest.raises(ValueError, match="independent"):
        build_generated_migration_reproduction_receipt(**values)
