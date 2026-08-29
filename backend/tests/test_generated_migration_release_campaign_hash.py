from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.artifact_manifest import artifact_manifest_hash
from app.generated_migration_benchmark import GeneratedMigrationBenchmarkReport, MigrationBenchmarkRow
from app.generated_migration_campaign import run_generated_migration_campaign
from app.generated_migration_release_evidence import validate_generated_migration_campaign_payload
from app.machine_profile import machine_identity_document, machine_profile_fingerprint
from app.parser import parse_workload_text


REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX = REPO_ROOT / "research" / "matrices" / "rq7-generated-migration.json"
EXAMPLE = REPO_ROOT / "examples" / "users-demo.yaml"


def _machine() -> dict[str, object]:
    profile: dict[str, object] = {
        "schema_version": 2,
        "protocol": "morpheus-machine-profile-v2",
        "captured_at": "2026-08-29T00:00:00+00:00",
        "source_commit": "a" * 40,
        "platform": {"system": "TestOS", "release": "1", "version": "1", "machine": "x86_64", "processor": "test", "python": "3.14.0"},
        "cpu": {"logical_count": 8, "linux": {}, "windows": {}},
        "toolchain": {"compiler": "/fake/g++", "compiler_kind": "gnu", "compiler_version": "fake 1", "cmake": "fake", "git": "fake"},
        "environment": {"python_executable": "/fake/python", "temp": "/tmp"},
        "truth_note": "test fixture",
    }
    profile["machine_fingerprint_sha256"] = machine_profile_fingerprint(profile)
    profile["machine_identity"] = machine_identity_document(profile)
    return profile


def _benchmark(bundle, spec, *, config, compile_timeout_seconds, run_timeout_seconds):
    rows = tuple(
        MigrationBenchmarkRow(i, config.readers, config.transitions, config.record_count, 1000 + i, 100 + i, 1000 + i, 0)
        for i in range(config.repetitions)
    )
    return GeneratedMigrationBenchmarkReport(
        True,
        "MEASURED_LOCAL_PROCESS_GENERATED_MIGRATION_TRANSITION_COST",
        bundle.source_candidate_id,
        bundle.target_candidate_id,
        bundle.source_manifest.workload_ir_hash,
        bundle.source_manifest.configuration_ir_hash,
        bundle.target_manifest.configuration_ir_hash,
        artifact_manifest_hash(bundle.source_manifest),
        artifact_manifest_hash(bundle.target_manifest),
        bundle.source_manifest.source_sha256,
        bundle.target_manifest.source_sha256,
        "b" * 64,
        "/fake/g++",
        "gnu",
        "fake 1",
        config,
        rows,
        0,
        0,
    )


def _payload() -> dict:
    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    campaign = run_generated_migration_campaign(
        spec,
        matrix,
        benchmark_fn=_benchmark,
        machine_profile_fn=_machine,
        limit=2,
    )
    return campaign.as_dict()


def test_release_validator_accepts_real_campaign_envelope_hash() -> None:
    validate_generated_migration_campaign_payload(_payload())


def test_release_validator_rejects_top_level_campaign_hash_forgery() -> None:
    payload = _payload()
    payload["campaign_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="campaign_sha256"):
        validate_generated_migration_campaign_payload(payload)
