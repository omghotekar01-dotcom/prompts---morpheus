from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.artifact_manifest import artifact_manifest_hash
from app.generated_migration_benchmark import GeneratedMigrationBenchmarkReport, MigrationBenchmarkRow
from app.generated_migration_campaign import freeze_generated_migration_campaign, run_generated_migration_campaign, summarize_generated_migration_campaign
from app.generated_migration_transition_evidence import build_generated_migration_transition_cost_evidence
from app.machine_profile import machine_identity_document, machine_profile_fingerprint
from app.parser import parse_workload_text
from app.release_evidence_validation import validate_release_evidence_bytes
from app.rq7_confirmatory_analysis import analyze_rq7_confirmatory
from app.rq7_confirmatory_links import validate_rq7_confirmatory_cross_links


REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = REPO_ROOT / "research" / "matrices" / "rq7-generated-migration.json"
EXAMPLE = REPO_ROOT / "examples" / "users-demo.yaml"


def _canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _matrix() -> dict[str, object]:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def _machine() -> dict[str, object]:
    profile: dict[str, object] = {
        "schema_version": 2,
        "protocol": "morpheus-machine-profile-v2",
        "captured_at": "2026-08-29T00:00:00+00:00",
        "source_commit": "a" * 40,
        "platform": {"system": "TestOS", "release": "1", "version": "1", "machine": "x86_64", "processor": "test", "python": "3.14.0"},
        "cpu": {"logical_count": 16, "linux": {}, "windows": {}},
        "toolchain": {"compiler": "/fake/g++", "compiler_kind": "gnu", "compiler_version": "fake 1", "cmake": "fake", "git": "fake"},
        "environment": {"python_executable": "/fake/python", "temp": "/tmp"},
        "truth_note": "test fixture",
    }
    profile["machine_fingerprint_sha256"] = machine_profile_fingerprint(profile)
    profile["machine_identity"] = machine_identity_document(profile)
    return profile


def _benchmark(bundle, spec, *, config, compile_timeout_seconds, run_timeout_seconds):
    reader_factor = {1: 1.0, 4: 1.1, 16: 1.3}[config.readers]
    transition_factor = {10: 1.0, 100: 1.02}[config.transitions]
    rows = tuple(
        MigrationBenchmarkRow(
            i,
            config.readers,
            config.transitions,
            config.record_count,
            int(config.record_count * 100 * reader_factor * transition_factor) + i + 1,
            int(2000 * reader_factor) + i + 1,
            5000 + i,
            0,
        )
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


def _evidence_chain():
    matrix = _matrix()
    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    campaign = run_generated_migration_campaign(spec, matrix, benchmark_fn=_benchmark, machine_profile_fn=_machine)
    summary = summarize_generated_migration_campaign(campaign)
    attestation = build_generated_migration_transition_cost_evidence(campaign, summary=summary)
    experiment = freeze_generated_migration_campaign(matrix).as_dict()
    analysis = analyze_rq7_confirmatory(campaign)
    artifacts = {
        "rq7_confirmatory_analysis": {"json": analysis, "canonical_json_sha256": _canonical(analysis)},
        "generated_migration_campaign": {"json": campaign.as_dict(), "canonical_json_sha256": _canonical(campaign.as_dict())},
        "generated_migration_campaign_summary": {"json": summary, "canonical_json_sha256": _canonical(summary)},
        "generated_migration_transition_cost_evidence": {"json": attestation, "canonical_json_sha256": _canonical(attestation)},
        "machine_profile": {"json": campaign.machine_profile, "canonical_json_sha256": _canonical(campaign.machine_profile)},
        "experiment_manifest": {"json": experiment, "canonical_json_sha256": _canonical(experiment)},
    }
    return analysis, artifacts


def test_h7_confirmatory_analysis_is_strict_release_evidence() -> None:
    analysis, _ = _evidence_chain()
    result = validate_release_evidence_bytes("rq7_confirmatory_analysis", json.dumps(analysis).encode())
    assert result.valid is True

    forged = dict(analysis)
    forged["analysis_sha256"] = "0" * 64
    bad = validate_release_evidence_bytes("rq7_confirmatory_analysis", json.dumps(forged).encode())
    assert bad.valid is False
    assert "analysis_sha256" in bad.details[0]


def test_h7_cross_links_accept_matching_complete_local_chain() -> None:
    _, artifacts = _evidence_chain()
    assert validate_rq7_confirmatory_cross_links(artifacts) == []


def test_h7_cross_links_reject_self_consistent_but_wrong_campaign_identity() -> None:
    analysis, artifacts = _evidence_chain()
    forged = dict(analysis)
    forged["campaign_sha256"] = "f" * 64
    forged["analysis_sha256"] = _canonical({key: value for key, value in forged.items() if key != "analysis_sha256"})
    assert validate_release_evidence_bytes("rq7_confirmatory_analysis", json.dumps(forged).encode()).valid is True
    artifacts["rq7_confirmatory_analysis"] = {"json": forged, "canonical_json_sha256": _canonical(forged)}
    errors = validate_rq7_confirmatory_cross_links(artifacts)
    assert any("campaign_sha256" in error for error in errors)
