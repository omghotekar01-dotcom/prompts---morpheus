from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.artifact_manifest import artifact_manifest_hash
from app.generated_migration_benchmark import GeneratedMigrationBenchmarkReport, MigrationBenchmarkRow
from app.generated_migration_campaign import run_generated_migration_campaign
from app.generated_migration_campaign_io import load_generated_migration_campaign
from app.machine_profile import machine_identity_document, machine_profile_fingerprint
from app.parser import parse_workload_text
from app.rq7_confirmatory_analysis import analyze_rq7_confirmatory


REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = REPO_ROOT / "research" / "matrices" / "rq7-generated-migration.json"
EXAMPLE = REPO_ROOT / "examples" / "users-demo.yaml"
ANALYZE_SCRIPT = REPO_ROOT / "scripts" / "analyze_rq7_generated_migration.py"


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
        "toolchain": {
            "compiler": "/fake/g++",
            "compiler_kind": "gnu",
            "compiler_version": "fake-g++ 1.0",
            "cmake": "cmake fake",
            "git": "git fake",
        },
        "environment": {"python_executable": "/fake/python", "temp": "/tmp"},
        "truth_note": "test fixture",
    }
    profile["machine_fingerprint_sha256"] = machine_profile_fingerprint(profile)
    profile["machine_identity"] = machine_identity_document(profile)
    return profile


def _report(bundle, config, *, ci: bool = False) -> GeneratedMigrationBenchmarkReport:
    reader_factor = {1: 1.0, 4: 1.10, 16: 1.30}[config.readers]
    transition_factor = {10: 1.0, 100: 1.02}[config.transitions]
    rows = tuple(
        MigrationBenchmarkRow(
            repetition=index,
            readers=config.readers,
            transitions=config.transitions,
            record_count=config.record_count,
            migrate_validate_activate_ns_per=int(config.record_count * 100 * reader_factor * transition_factor) + index + 1,
            rollback_ns_per=int(2_000 * reader_factor) + index + 1,
            reads=10_000 + index,
            invalid_reads=0,
        )
        for index in range(config.repetitions)
    )
    return GeneratedMigrationBenchmarkReport(
        success=True,
        evidence_state=(
            "MEASURED_CI_SMOKE_GENERATED_MIGRATION_TRANSITION_COST"
            if ci
            else "MEASURED_LOCAL_PROCESS_GENERATED_MIGRATION_TRANSITION_COST"
        ),
        source_candidate_id=bundle.source_candidate_id,
        target_candidate_id=bundle.target_candidate_id,
        workload_ir_hash=bundle.source_manifest.workload_ir_hash,
        source_configuration_ir_hash=bundle.source_manifest.configuration_ir_hash,
        target_configuration_ir_hash=bundle.target_manifest.configuration_ir_hash,
        source_manifest_sha256=artifact_manifest_hash(bundle.source_manifest),
        target_manifest_sha256=artifact_manifest_hash(bundle.target_manifest),
        source_header_sha256=bundle.source_manifest.source_sha256,
        target_header_sha256=bundle.target_manifest.source_sha256,
        benchmark_source_sha256="d" * 64,
        compiler="/fake/g++",
        compiler_kind="gnu",
        compiler_version="fake-g++ 1.0",
        config=config,
        rows=rows,
        compile_returncode=0,
        run_returncode=0,
    )


def _local_benchmark(bundle, spec, *, config, compile_timeout_seconds, run_timeout_seconds):
    return _report(bundle, config)


def _ci_benchmark(bundle, spec, *, config, compile_timeout_seconds, run_timeout_seconds):
    return _report(bundle, config, ci=True)


def _campaign(*, benchmark_fn=_local_benchmark, limit=None):
    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    return run_generated_migration_campaign(
        spec,
        _matrix(),
        benchmark_fn=benchmark_fn,
        machine_profile_fn=_machine,
        limit=limit,
    )


def test_h7_confirmatory_analysis_uses_matched_blocks_and_recovers_known_effects() -> None:
    campaign = _campaign()
    analysis = analyze_rq7_confirmatory(campaign)

    assert analysis["schema"] == "morpheus-rq7-confirmatory-analysis-v1"
    assert analysis["evidence_state"] == "CONFIRMATORY_ANALYSIS_OF_COMPLETE_LOCAL_RQ7_CAMPAIGN"
    assert analysis["raw_repetitions_are_not_independent_workloads"] is True
    assert analysis["h7_decision"] == "SUPPORTED_WITHIN_FROZEN_SINGLE_MACHINE_SCOPE"
    assert len(analysis["analysis_sha256"]) == 64

    record = analysis["record_count_effect"]
    assert record["block_count"] == 6
    assert record["confirmatory_decision_alpha_0_05"] == "SUPPORTED"
    assert 1.95 < record["geometric_mean_cost_ratio_per_record_doubling"] < 2.05
    assert record["bootstrap_95_ci_cost_ratio_per_doubling"][0] > 1.0

    reader = analysis["reader_pressure_sensitivity"]
    assert reader["contrasts"]["readers_4_vs_1"]["block_count"] == 8
    assert reader["contrasts"]["readers_16_vs_1"]["block_count"] == 8
    assert all(item["rejected"] is True for item in reader["multiple_comparison_correction"]["hypotheses"])
    assert reader["contrasts"]["readers_16_vs_1"]["geometric_mean_ratio"] > reader["contrasts"]["readers_4_vs_1"]["geometric_mean_ratio"] > 1.0

    transition = analysis["transition_count_robustness"]
    assert transition["block_count"] == 12
    assert 1.0 < transition["geometric_mean_ratio"] < 1.05

    model = analysis["global_log_cost_model"]
    assert model["cell_count"] == 24
    assert len(model["residuals"]) == 24
    assert model["r_squared"] > 0.999

    assert len(analysis["raw_cells"]) == 24
    assert all(len(cell["migrate_validate_activate_ns_per"]) == 10 for cell in analysis["raw_cells"])
    assert analysis["reader_safety"]["invalid_reader_observations"] == 0


def test_persisted_campaign_round_trips_through_strict_loader() -> None:
    original = _campaign()
    loaded = load_generated_migration_campaign(original.as_dict())
    assert loaded.campaign_sha256 == original.campaign_sha256
    assert loaded.machine_fingerprint_sha256 == original.machine_fingerprint_sha256
    assert [entry.report_sha256 for entry in loaded.entries] == [entry.report_sha256 for entry in original.entries]
    assert analyze_rq7_confirmatory(loaded)["analysis_sha256"] == analyze_rq7_confirmatory(original)["analysis_sha256"]


def test_h7_offline_cli_analyzes_persisted_campaign_without_native_execution(tmp_path: Path) -> None:
    campaign_path = tmp_path / "campaign.json"
    output_path = tmp_path / "analysis.json"
    campaign_path.write_text(json.dumps(_campaign().as_dict(), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(ANALYZE_SCRIPT), str(campaign_path), "--output", str(output_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    analysis = json.loads(output_path.read_text(encoding="utf-8"))
    assert result["schema"] == "morpheus-rq7-confirmatory-analysis-run-v1"
    assert result["analysis_sha256"] == analysis["analysis_sha256"]
    assert analysis["h7_decision"] == "SUPPORTED_WITHIN_FROZEN_SINGLE_MACHINE_SCOPE"


def test_h7_offline_cli_rejects_forged_campaign_envelope(tmp_path: Path) -> None:
    payload = _campaign().as_dict()
    payload["campaign_sha256"] = "0" * 64
    campaign_path = tmp_path / "forged.json"
    output_path = tmp_path / "analysis.json"
    campaign_path.write_text(json.dumps(payload), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(ANALYZE_SCRIPT), str(campaign_path), "--output", str(output_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 2
    assert "campaign_sha256" in completed.stderr
    assert not output_path.exists()


def test_h7_confirmatory_analysis_rejects_partial_campaign() -> None:
    with pytest.raises(ValueError, match="complete comparable"):
        analyze_rq7_confirmatory(_campaign(limit=23))


def test_h7_confirmatory_analysis_rejects_ci_smoke_campaign() -> None:
    campaign = _campaign(benchmark_fn=_ci_benchmark)
    assert campaign.evidence_state == "GENERATED_MIGRATION_CAMPAIGN_COMPLETE_CI_SMOKE"
    with pytest.raises(ValueError, match="non-CI local"):
        analyze_rq7_confirmatory(campaign)
