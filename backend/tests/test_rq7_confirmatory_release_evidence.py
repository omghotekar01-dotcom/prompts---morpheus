from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app import measurement_environment as env
from app.artifact_manifest import artifact_manifest_hash
from app.generated_migration_benchmark import GeneratedMigrationBenchmarkReport, MigrationBenchmarkRow
from app.generated_migration_campaign import freeze_generated_migration_campaign, run_generated_migration_campaign, summarize_generated_migration_campaign
from app.generated_migration_transition_evidence import build_generated_migration_transition_cost_evidence
from app.machine_profile import machine_identity_document, machine_profile_fingerprint
from app.parser import parse_workload_text
from app.release_evidence_validation import validate_release_evidence_bytes
from app.rq7_analysis_provenance import ANALYSIS_SOURCE_PATH, build_rq7_analysis_provenance
from app.rq7_confirmatory_analysis import analyze_rq7_confirmatory
from app.rq7_confirmatory_links import validate_rq7_confirmatory_cross_links
from app.rq7_record_count_effect_evidence import build_rq7_record_count_effect_evidence


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
        "platform": {"system": "Linux", "release": "1", "version": "1", "machine": "x86_64", "processor": "test", "python": "3.14.0"},
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


def _snapshot(*, timestamp: str, platform_name: str = "Linux", affinity: list[int] | None = None) -> dict:
    linux = platform_name == "Linux"
    core = {
        "schema": env.SNAPSHOT_SCHEMA,
        "captured_at": timestamp,
        "platform": platform_name,
        "logical_cpu_count": 16,
        "process_affinity": list(range(16)) if affinity is None else affinity,
        "load_average": {
            "one_minute": 0.8,
            "five_minutes": 0.5,
            "fifteen_minutes": 0.3,
            "one_minute_per_logical_cpu": 0.05,
        },
        "linux_scaling_governors": {"cpu0": "performance"} if linux else {},
        "linux_frequency_summary": {
            "observed_cpu_count": 1,
            "min_khz": 2_000_000,
            "mean_khz": 2_000_000.0,
            "max_khz": 2_000_000,
        } if linux else None,
        "windows_active_power_scheme": None if linux else "High performance",
        "thermal_summary": None,
        "github_actions": False,
        "evidence_state": env.SNAPSHOT_EVIDENCE_STATE,
        "truth_boundary": env._SNAPSHOT_TRUTH_BOUNDARY,
    }
    return {**core, "snapshot_sha256": _canonical(core)}


def _environment(campaign, analysis, *, platform_name: str = "Linux", unstable_affinity: bool = False, resumed: bool = False):
    start = _snapshot(timestamp="2026-08-29T09:00:00+00:00", platform_name=platform_name)
    end_affinity = list(range(15)) if unstable_affinity else None
    end = _snapshot(timestamp="2026-08-29T09:10:00+00:00", platform_name=platform_name, affinity=end_affinity)
    ids = [str(cell["experiment_id"]) for cell in analysis["raw_cells"]]
    if resumed:
        ids = ids[:12]
    return env.build_measurement_environment_record(
        start,
        end,
        campaign_sha256=campaign.campaign_sha256,
        machine_fingerprint_sha256=campaign.machine_fingerprint_sha256,
        covered_experiment_ids=ids,
        planned_experiments=24,
        resumed_from_campaign_sha256="e" * 64 if resumed else None,
    )


def _evidence_chain(*, with_environment: bool = True, with_positive_effect: bool = True):
    matrix = _matrix()
    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    campaign = run_generated_migration_campaign(spec, matrix, benchmark_fn=_benchmark, machine_profile_fn=_machine)
    summary = summarize_generated_migration_campaign(campaign)
    transition_attestation = build_generated_migration_transition_cost_evidence(campaign, summary=summary)
    experiment = freeze_generated_migration_campaign(matrix).as_dict()
    analysis = analyze_rq7_confirmatory(campaign)
    source_bytes = ANALYSIS_SOURCE_PATH.read_bytes()
    provenance = build_rq7_analysis_provenance(analysis, source_bytes=source_bytes)
    artifacts = {
        "rq7_confirmatory_analysis": {"json": analysis, "canonical_json_sha256": _canonical(analysis)},
        "rq7_analysis_provenance": {"json": provenance, "canonical_json_sha256": _canonical(provenance)},
        "rq7_analysis_source": {"json": None, "sha256": hashlib.sha256(source_bytes).hexdigest()},
        "generated_migration_campaign": {"json": campaign.as_dict(), "canonical_json_sha256": _canonical(campaign.as_dict())},
        "generated_migration_campaign_summary": {"json": summary, "canonical_json_sha256": _canonical(summary)},
        "generated_migration_transition_cost_evidence": {"json": transition_attestation, "canonical_json_sha256": _canonical(transition_attestation)},
        "machine_profile": {"json": campaign.machine_profile, "canonical_json_sha256": _canonical(campaign.machine_profile)},
        "experiment_manifest": {"json": experiment, "canonical_json_sha256": _canonical(experiment)},
    }
    environment = None
    if with_environment:
        environment = _environment(campaign, analysis)
        artifacts["measurement_environment_record"] = {
            "json": environment,
            "canonical_json_sha256": _canonical(environment),
        }
    if with_positive_effect and environment is not None:
        effect = build_rq7_record_count_effect_evidence(analysis, provenance, environment)
        artifacts["rq7_record_count_effect_evidence"] = {
            "json": effect,
            "canonical_json_sha256": _canonical(effect),
        }
    return campaign, analysis, artifacts


def test_h7_confirmatory_analysis_and_positive_effect_are_strict_release_evidence() -> None:
    _, analysis, artifacts = _evidence_chain()
    analysis_result = validate_release_evidence_bytes("rq7_confirmatory_analysis", json.dumps(analysis).encode())
    assert analysis_result.valid is True
    effect = artifacts["rq7_record_count_effect_evidence"]["json"]
    effect_result = validate_release_evidence_bytes("rq7_record_count_effect_evidence", json.dumps(effect).encode())
    assert effect_result.valid is True

    forged = dict(analysis)
    forged["analysis_sha256"] = "0" * 64
    bad = validate_release_evidence_bytes("rq7_confirmatory_analysis", json.dumps(forged).encode())
    assert bad.valid is False
    assert "analysis_sha256" in bad.details[0]


def test_h7_cross_links_accept_complete_positive_authority_chain() -> None:
    _, _, artifacts = _evidence_chain()
    assert validate_rq7_confirmatory_cross_links(artifacts) == []


def test_h7_cross_links_reject_self_consistent_but_wrong_campaign_identity() -> None:
    _, analysis, artifacts = _evidence_chain()
    forged = dict(analysis)
    forged["campaign_sha256"] = "f" * 64
    forged["analysis_sha256"] = _canonical({key: value for key, value in forged.items() if key != "analysis_sha256"})
    assert validate_release_evidence_bytes("rq7_confirmatory_analysis", json.dumps(forged).encode()).valid is True
    artifacts["rq7_confirmatory_analysis"] = {"json": forged, "canonical_json_sha256": _canonical(forged)}
    errors = validate_rq7_confirmatory_cross_links(artifacts)
    assert any("campaign_sha256" in error for error in errors)


def test_h7_cross_links_reject_transplanted_analysis_source_bytes() -> None:
    _, _, artifacts = _evidence_chain()
    artifacts["rq7_analysis_source"]["sha256"] = "f" * 64
    errors = validate_rq7_confirmatory_cross_links(artifacts)
    assert any("source hash does not match packaged analysis source bytes" in error for error in errors)


def test_h7_cross_links_reject_transplanted_positive_effect_attestation() -> None:
    _, _, artifacts = _evidence_chain()
    effect = dict(artifacts["rq7_record_count_effect_evidence"]["json"])
    effect["analysis_provenance_sha256"] = "f" * 64
    artifacts["rq7_record_count_effect_evidence"] = {"json": effect, "canonical_json_sha256": _canonical(effect)}
    errors = validate_rq7_confirmatory_cross_links(artifacts)
    assert any("provenance hash" in error for error in errors)


def test_h7_cross_links_reject_environment_from_different_machine_platform() -> None:
    campaign, analysis, artifacts = _evidence_chain(with_environment=False, with_positive_effect=False)
    environment = _environment(campaign, analysis, platform_name="Windows")
    assert validate_release_evidence_bytes("measurement_environment_record", json.dumps(environment).encode()).valid is True
    artifacts["measurement_environment_record"] = {"json": environment, "canonical_json_sha256": _canonical(environment)}

    errors = validate_rq7_confirmatory_cross_links(artifacts)
    assert any("platform does not match" in error for error in errors)


def test_h7_cross_links_reject_unstable_process_affinity() -> None:
    campaign, analysis, artifacts = _evidence_chain(with_environment=False, with_positive_effect=False)
    environment = _environment(campaign, analysis, unstable_affinity=True)
    assert environment["observed_stability"]["process_affinity_stable"] is False
    artifacts["measurement_environment_record"] = {"json": environment, "canonical_json_sha256": _canonical(environment)}

    errors = validate_rq7_confirmatory_cross_links(artifacts)
    assert any("stable process affinity" in error for error in errors)


def test_h7_cross_links_reject_resumed_partial_environment_coverage() -> None:
    campaign, analysis, artifacts = _evidence_chain(with_environment=False, with_positive_effect=False)
    environment = _environment(campaign, analysis, resumed=True)
    assert environment["coverage"]["complete_single_invocation_coverage"] is False
    artifacts["measurement_environment_record"] = {"json": environment, "canonical_json_sha256": _canonical(environment)}

    errors = validate_rq7_confirmatory_cross_links(artifacts)
    assert any("complete single-invocation" in error for error in errors)
    assert any("does not accept a resumed" in error for error in errors)
    assert any("does not match all 24" in error for error in errors)
