from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.artifact_manifest import artifact_manifest_hash
from app.generated_migration_verifier import GeneratedMigrationVerificationResult
from app.server import app


REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "examples" / "users-demo.yaml"
client = TestClient(app)


def _fake_success(bundle):
    return GeneratedMigrationVerificationResult(
        success=True,
        evidence_state="COMPILE_AND_EXECUTION_VERIFIED_LOCAL_GENERATED_MIGRATION",
        source_candidate_id=bundle.source_candidate_id,
        target_candidate_id=bundle.target_candidate_id,
        source_manifest_sha256=artifact_manifest_hash(bundle.source_manifest),
        target_manifest_sha256=artifact_manifest_hash(bundle.target_manifest),
        harness_sha256=bundle.harness_sha256,
        compiler="/fake/morpheus-cxx",
        compiler_kind="gnu",
        compiler_version="fake compiler 1.0",
        compile_returncode=0,
        run_returncode=0,
        source_reads=11,
        target_reads=13,
        invalid_reads=0,
        final_generation=4,
        run_stdout=(
            "MORPHEUS_GENERATED_MIGRATION_OK source_reads=11 target_reads=13 "
            "invalid_reads=0 final_generation=4\n"
        ),
    )


def test_generated_migration_verify_api_persists_content_addressed_evidence(monkeypatch) -> None:
    monkeypatch.setattr("app.advanced_api.verify_generated_migration_bundle", _fake_success)
    response = client.post(
        "/api/v2/migration/generated/verify",
        json={
            "spec_text": EXAMPLE.read_text(encoding="utf-8"),
            "record_count": 16,
            "compile_timeout_seconds": 5,
            "run_timeout_seconds": 5,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source_candidate_id"] != payload["target_candidate_id"]
    assert payload["verification"]["success"] is True
    assert payload["verification"]["invalid_reads"] == 0
    assert payload["verification"]["evidence_state"] == "COMPILE_AND_EXECUTION_VERIFIED_LOCAL_GENERATED_MIGRATION"

    source_artifact = payload["source_header_artifact"]
    target_artifact = payload["target_header_artifact"]
    harness_artifact = payload["migration_harness_artifact"]
    manifest_artifact = payload["verification_manifest_artifact"]
    assert source_artifact["kind"] == "generated_cpp20_header"
    assert target_artifact["kind"] == "generated_cpp20_header"
    assert harness_artifact["kind"] == "generated_migration_harness"
    assert manifest_artifact["kind"] == "generated_migration_verification_manifest"
    assert len(source_artifact["sha256"]) == 64
    assert len(target_artifact["sha256"]) == 64
    assert len(harness_artifact["sha256"]) == 64
    assert len(manifest_artifact["sha256"]) == 64
    assert manifest_artifact["evidence_state"] == "COMPILE_AND_EXECUTION_VERIFIED_LOCAL_GENERATED_MIGRATION"
    assert "neither mutates a live deployment" in payload["truth_boundary"]

    stored = client.get(f"/api/artifacts/{manifest_artifact['sha256']}")
    assert stored.status_code == 200
    assert stored.json()["metadata"]["kind"] == "generated_migration_verification_manifest"
    assert "COMPILE_AND_EXECUTION_VERIFIED_LOCAL_GENERATED_MIGRATION" in stored.json()["content"]


def test_generated_migration_verify_api_persists_failed_local_evidence(monkeypatch) -> None:
    def fake_failure(bundle):
        return GeneratedMigrationVerificationResult(
            success=False,
            evidence_state="COMPILER_UNAVAILABLE",
            source_candidate_id=bundle.source_candidate_id,
            target_candidate_id=bundle.target_candidate_id,
            source_manifest_sha256=artifact_manifest_hash(bundle.source_manifest),
            target_manifest_sha256=artifact_manifest_hash(bundle.target_manifest),
            harness_sha256=bundle.harness_sha256,
            compiler=None,
            compiler_kind=None,
            compiler_version=None,
            compile_returncode=None,
            run_returncode=None,
        )

    monkeypatch.setattr("app.advanced_api.verify_generated_migration_bundle", fake_failure)
    response = client.post(
        "/api/v2/migration/generated/verify",
        json={
            "spec_text": EXAMPLE.read_text(encoding="utf-8"),
            "record_count": 8,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["verification"]["success"] is False
    assert payload["verification"]["evidence_state"] == "COMPILER_UNAVAILABLE"
    assert payload["verification_manifest_artifact"]["evidence_state"] == "COMPILER_UNAVAILABLE"
    assert payload["verification_manifest_artifact"]["kind"] == "generated_migration_verification_manifest"
