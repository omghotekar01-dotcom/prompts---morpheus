from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.reproducibility import (
    EvidenceFile,
    build_release_reproducibility_manifest,
    build_reproducibility_manifest,
    hash_evidence_files,
)


def test_reproducibility_manifest_hashes_and_orders_roles_deterministically(tmp_path: Path) -> None:
    workload = tmp_path / "workload.yaml"
    workload.write_text("name: test\n", encoding="utf-8")
    measurements = tmp_path / "measurements.json"
    measurements.write_text('{"value": 1}\n', encoding="utf-8")

    manifest = build_reproducibility_manifest(
        [
            EvidenceFile("measurements", measurements),
            EvidenceFile("workload", workload),
        ],
        source_commit="abc123",
    )

    assert manifest["source_commit"] == "abc123"
    assert manifest["evidence_state"] == "REPRODUCIBILITY_MANIFEST_NOT_EXTERNAL_ATTESTATION"
    files = manifest["files"]
    assert [item["role"] for item in files] == ["measurements", "workload"]
    assert files[1]["sha256"] == hashlib.sha256(workload.read_bytes()).hexdigest()
    assert len(str(manifest["aggregate_evidence_sha256"])) == 64


def test_release_reproducibility_binds_commit_api_and_feature_policy(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    evidence.write_text('{"evidence": true}\n', encoding="utf-8")
    files = [EvidenceFile("evidence", evidence)]

    first = build_release_reproducibility_manifest(
        files,
        source_commit="a" * 40,
        api_contract_sha256="b" * 64,
        feature_registry_sha256="c" * 64,
    )
    second = build_release_reproducibility_manifest(
        files,
        source_commit="a" * 40,
        api_contract_sha256="b" * 64,
        feature_registry_sha256="c" * 64,
    )
    changed_policy = build_release_reproducibility_manifest(
        files,
        source_commit="a" * 40,
        api_contract_sha256="b" * 64,
        feature_registry_sha256="d" * 64,
    )

    assert first == second
    assert first["schema_version"] == 2
    assert first["protocol"] == "morpheus-release-reproducibility-manifest-v2"
    assert first["source_commit"] == "a" * 40
    assert first["contract_fingerprints"] == {
        "api_contract_sha256": "b" * 64,
        "feature_registry_sha256": "c" * 64,
    }
    assert len(first["manifest_sha256"]) == 64
    assert first["aggregate_evidence_sha256"] != changed_policy["aggregate_evidence_sha256"]
    assert first["manifest_sha256"] != changed_policy["manifest_sha256"]


def test_release_reproducibility_rejects_weak_identity(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    files = [EvidenceFile("evidence", evidence)]

    with pytest.raises(ValueError, match="40-character"):
        build_release_reproducibility_manifest(
            files,
            source_commit="abc123",
            api_contract_sha256="b" * 64,
            feature_registry_sha256="c" * 64,
        )
    with pytest.raises(ValueError, match="api_contract_sha256"):
        build_release_reproducibility_manifest(
            files,
            source_commit="a" * 40,
            api_contract_sha256="bad",
            feature_registry_sha256="c" * 64,
        )
    with pytest.raises(ValueError, match="feature_registry_sha256"):
        build_release_reproducibility_manifest(
            files,
            source_commit="a" * 40,
            api_contract_sha256="b" * 64,
            feature_registry_sha256="bad",
        )


def test_reproducibility_manifest_rejects_duplicate_roles_and_missing_files(tmp_path: Path) -> None:
    existing = tmp_path / "one.txt"
    existing.write_text("one", encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate evidence role"):
        hash_evidence_files([EvidenceFile("same", existing), EvidenceFile("same", existing)])

    with pytest.raises(ValueError, match="does not exist"):
        hash_evidence_files([EvidenceFile("missing", tmp_path / "missing.txt")])
