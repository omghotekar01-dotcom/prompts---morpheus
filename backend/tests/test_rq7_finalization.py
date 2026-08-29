from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import measurement_environment as env
from app.artifact_manifest import artifact_manifest_hash
from app.generated_migration_benchmark import GeneratedMigrationBenchmarkReport, MigrationBenchmarkRow
from app.generated_migration_campaign import freeze_generated_migration_campaign, run_generated_migration_campaign, summarize_generated_migration_campaign
from app.generated_migration_transition_evidence import build_generated_migration_transition_cost_evidence
from app.machine_profile import machine_identity_document, machine_profile_fingerprint
from app.parser import parse_workload_text
from app.rq7_confirmatory_analysis import analyze_rq7_confirmatory
from scripts.finalize_rq7_evidence import finalize_rq7_evidence


MATRIX_PATH = REPO_ROOT / "research" / "matrices" / "rq7-generated-migration.json"
EXAMPLE = REPO_ROOT / "examples" / "users-demo.yaml"


def _canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _matrix() -> dict[str, object]:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def _machine() -> dict[str, object]:
    profile: dict[str, object] = {
        "schema_version": 2,
        "protocol": "morpheus-machine-profile-v2",
        "captured_at": "2026-08-29T00:00:00+00:00",
        "source_commit": "a" * 40,
        "platform": {"system": "Linux", "release": "1", "version": "1", "machine": "x86_64", "processor": "test", "python": "3.14.0"},
        "cpu": {"logical_count": 8, "linux": {}, "windows": {}},
        "toolchain": {"compiler": "/fake/g++", "compiler_kind": "gnu", "compiler_version": "fake 1", "cmake": "fake", "git": "fake"},
        "environment": {"python_executable": "/fake/python", "temp": "/tmp"},
        "truth_note": "test fixture",
    }
    profile["machine_fingerprint_sha256"] = machine_profile_fingerprint(profile)
    profile["machine_identity"] = machine_identity_document(profile)
    return profile


def _benchmark_factory(*, record_effect: bool):
    def benchmark(bundle, spec, *, config, compile_timeout_seconds, run_timeout_seconds):
        reader_factor = {1: 1.0, 4: 1.1, 16: 1.3}[config.readers]
        transition_factor = {10: 1.0, 100: 1.02}[config.transitions]
        state_factor = config.record_count if record_effect else 4096
        rows = tuple(
            MigrationBenchmarkRow(
                i,
                config.readers,
                config.transitions,
                config.record_count,
                int(state_factor * 100 * reader_factor * transition_factor) + i + 1,
                int(2000 * reader_factor) + i + 1,
                7000 + i,
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

    return benchmark


def _snapshot(timestamp: str) -> dict:
    core = {
        "schema": env.SNAPSHOT_SCHEMA,
        "captured_at": timestamp,
        "platform": "Linux",
        "logical_cpu_count": 8,
        "process_affinity": list(range(8)),
        "load_average": {"one_minute": 0.8, "five_minutes": 0.5, "fifteen_minutes": 0.3, "one_minute_per_logical_cpu": 0.1},
        "linux_scaling_governors": {"cpu0": "performance"},
        "linux_frequency_summary": {"observed_cpu_count": 1, "min_khz": 2_000_000, "mean_khz": 2_000_000.0, "max_khz": 2_000_000},
        "windows_active_power_scheme": None,
        "thermal_summary": None,
        "github_actions": False,
        "evidence_state": env.SNAPSHOT_EVIDENCE_STATE,
        "truth_boundary": env._SNAPSHOT_TRUTH_BOUNDARY,
    }
    return {**core, "snapshot_sha256": _canonical(core)}


def _prepare_run_dir(tmp_path: Path, *, record_effect: bool) -> tuple[Path, str]:
    matrix = _matrix()
    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    campaign = run_generated_migration_campaign(
        spec,
        matrix,
        benchmark_fn=_benchmark_factory(record_effect=record_effect),
        machine_profile_fn=_machine,
    )
    summary = summarize_generated_migration_campaign(campaign)
    transition = build_generated_migration_transition_cost_evidence(campaign, summary=summary)
    manifest = freeze_generated_migration_campaign(matrix).as_dict()
    analysis = analyze_rq7_confirmatory(campaign)
    environment = env.build_measurement_environment_record(
        _snapshot("2026-08-29T09:00:00+00:00"),
        _snapshot("2026-08-29T09:10:00+00:00"),
        campaign_sha256=campaign.campaign_sha256,
        machine_fingerprint_sha256=campaign.machine_fingerprint_sha256,
        covered_experiment_ids=[str(cell["experiment_id"]) for cell in analysis["raw_cells"]],
        planned_experiments=24,
    )

    run_dir = tmp_path / ("supported-run" if record_effect else "negative-run")
    run_dir.mkdir()
    _write_json(run_dir / "generated-migration-experiment-manifest.json", manifest)
    _write_json(run_dir / "generated-migration-machine-profile.json", campaign.machine_profile)
    _write_json(run_dir / "generated-migration-campaign.json", campaign.as_dict())
    _write_json(run_dir / "generated-migration-summary.json", summary)
    _write_json(run_dir / "generated-migration-transition-cost-evidence.json", transition)
    _write_json(run_dir / "generated-migration-measurement-environment.json", environment)
    return run_dir, analysis["h7_decision"]


def test_finalizer_mints_positive_h7_claim_only_for_supported_result(tmp_path: Path) -> None:
    run_dir, decision = _prepare_run_dir(tmp_path, record_effect=True)
    assert decision == "SUPPORTED_WITHIN_FROZEN_SINGLE_MACHINE_SCOPE"

    result = finalize_rq7_evidence(run_dir, tmp_path / "final-positive", version="0.10.0-rq7")
    descriptor = json.loads(Path(result["descriptor_path"]).read_text(encoding="utf-8"))
    package_manifest = json.loads((Path(result["package_dir"]) / "release-manifest.json").read_text(encoding="utf-8"))

    assert result["positive_effect_attestation_created"] is True
    assert result["positive_effect_not_created_reason"] is None
    assert Path(result["effect_attestation_path"]).is_file()
    assert {claim["type"] for claim in descriptor["claims"]} == {
        "generated_migration_transition_cost_measured",
        "rq7_systematic_record_count_effect",
    }
    roles = {item["role"] for item in descriptor["artifacts"]}
    assert {"rq7_analysis_source", "rq7_analysis_provenance", "rq7_record_count_effect_evidence"} <= roles
    assert package_manifest["release_state"] == "CLAIMS_EVIDENCE_COMPLETE"
    assert all(item["allowed"] is True for item in package_manifest["claim_gate"]["decisions"])


def test_finalizer_preserves_unconfirmed_h7_without_positive_claim(tmp_path: Path) -> None:
    run_dir, decision = _prepare_run_dir(tmp_path, record_effect=False)
    assert decision == "NOT_FULLY_CONFIRMED"

    result = finalize_rq7_evidence(run_dir, tmp_path / "final-negative", version="0.10.0-rq7")
    descriptor = json.loads(Path(result["descriptor_path"]).read_text(encoding="utf-8"))
    package_manifest = json.loads((Path(result["package_dir"]) / "release-manifest.json").read_text(encoding="utf-8"))

    assert result["positive_effect_attestation_created"] is False
    assert "did not produce" in result["positive_effect_not_created_reason"]
    assert result["effect_attestation_path"] is None
    assert [claim["type"] for claim in descriptor["claims"]] == ["generated_migration_transition_cost_measured"]
    assert "rq7_record_count_effect_evidence" not in {item["role"] for item in descriptor["artifacts"]}
    assert package_manifest["release_state"] == "CLAIMS_EVIDENCE_COMPLETE"
    assert package_manifest["claim_gate"]["decisions"][0]["allowed"] is True
