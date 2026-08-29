from __future__ import annotations

import json
from pathlib import Path

from app.artifact_manifest import artifact_manifest_hash
from app.generated_migration_benchmark import GeneratedMigrationBenchmarkReport, MigrationBenchmarkRow
from app.generated_migration_campaign import run_generated_migration_campaign
from app.machine_profile import machine_identity_document, machine_profile_fingerprint
from app.parser import parse_workload_text


REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = REPO_ROOT / "research" / "matrices" / "rq7-generated-migration.json"
EXAMPLE = REPO_ROOT / "examples" / "users-demo.yaml"


def _matrix() -> dict[str, object]:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def _machine() -> dict[str, object]:
    profile: dict[str, object] = {
        "schema_version": 2,
        "protocol": "morpheus-machine-profile-v2",
        "captured_at": "2026-08-29T00:00:00+00:00",
        "source_commit": "a" * 40,
        "platform": {"system": "TestOS", "release": "1", "version": "1", "machine": "x86_64", "processor": "test", "python": "3.14.0"},
        "cpu": {"logical_count": 8, "linux": {}, "windows": {}},
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


def _success(bundle, config) -> GeneratedMigrationBenchmarkReport:
    rows = tuple(
        MigrationBenchmarkRow(
            repetition=index,
            readers=config.readers,
            transitions=config.transitions,
            record_count=config.record_count,
            migrate_validate_activate_ns_per=10_000 + index,
            rollback_ns_per=1_000 + index,
            reads=2_000 + index,
            invalid_reads=0,
        )
        for index in range(config.repetitions)
    )
    return GeneratedMigrationBenchmarkReport(
        success=True,
        evidence_state="MEASURED_LOCAL_PROCESS_GENERATED_MIGRATION_TRANSITION_COST",
        source_candidate_id=bundle.source_candidate_id,
        target_candidate_id=bundle.target_candidate_id,
        workload_ir_hash=bundle.source_manifest.workload_ir_hash,
        source_configuration_ir_hash=bundle.source_manifest.configuration_ir_hash,
        target_configuration_ir_hash=bundle.target_manifest.configuration_ir_hash,
        source_manifest_sha256=artifact_manifest_hash(bundle.source_manifest),
        target_manifest_sha256=artifact_manifest_hash(bundle.target_manifest),
        source_header_sha256=bundle.source_manifest.source_sha256,
        target_header_sha256=bundle.target_manifest.source_sha256,
        benchmark_source_sha256="b" * 64,
        compiler="/fake/g++",
        compiler_kind="gnu",
        compiler_version="fake-g++ 1.0",
        config=config,
        rows=rows,
        compile_returncode=0,
        run_returncode=0,
    )


def _fake_success(bundle, spec, *, config, compile_timeout_seconds, run_timeout_seconds):
    return _success(bundle, config)


def test_checkpoint_callback_receives_monotonic_hash_bound_prefixes() -> None:
    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    snapshots = []
    final = run_generated_migration_campaign(
        spec,
        _matrix(),
        benchmark_fn=_fake_success,
        machine_profile_fn=_machine,
        checkpoint_callback=snapshots.append,
        limit=3,
    )
    assert [item.executed_experiments for item in snapshots] == [1, 2, 3]
    assert all(len(item.campaign_sha256) == 64 for item in snapshots)
    assert [entry.experiment_id for entry in snapshots[-1].entries] == [entry.experiment_id for entry in final.entries]
    assert snapshots[-1].campaign_sha256 == final.campaign_sha256


def test_all_requested_resume_cells_skip_native_prepare_and_execution(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    prior = run_generated_migration_campaign(
        spec,
        _matrix(),
        benchmark_fn=_fake_success,
        machine_profile_fn=_machine,
        limit=2,
    )

    def must_not_prepare(*args, **kwargs):
        raise AssertionError("fully resumed selection must not compile a benchmark")

    monkeypatch.setattr("app.generated_migration_campaign.prepare_generated_migration_benchmark", must_not_prepare)
    resumed = run_generated_migration_campaign(
        spec,
        _matrix(),
        machine_profile_fn=_machine,
        resume_checkpoint=prior.as_dict(),
        limit=2,
    )
    assert resumed.executed_experiments == 2
    assert resumed.campaign_sha256 == prior.campaign_sha256


def test_failed_cell_is_checkpointed_and_cannot_be_misread_as_partial_success() -> None:
    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    snapshots = []

    def fail(bundle, spec_arg, *, config, compile_timeout_seconds, run_timeout_seconds):
        return GeneratedMigrationBenchmarkReport(
            success=False,
            evidence_state="GENERATED_MIGRATION_BENCHMARK_RUN_FAILED",
            source_candidate_id=bundle.source_candidate_id,
            target_candidate_id=bundle.target_candidate_id,
            workload_ir_hash=bundle.source_manifest.workload_ir_hash,
            source_configuration_ir_hash=bundle.source_manifest.configuration_ir_hash,
            target_configuration_ir_hash=bundle.target_manifest.configuration_ir_hash,
            source_manifest_sha256=artifact_manifest_hash(bundle.source_manifest),
            target_manifest_sha256=artifact_manifest_hash(bundle.target_manifest),
            source_header_sha256=bundle.source_manifest.source_sha256,
            target_header_sha256=bundle.target_manifest.source_sha256,
            benchmark_source_sha256="c" * 64,
            compiler=None,
            compiler_kind=None,
            compiler_version=None,
            config=config,
            rows=(),
            compile_returncode=0,
            run_returncode=1,
        )

    campaign = run_generated_migration_campaign(
        spec,
        _matrix(),
        benchmark_fn=fail,
        machine_profile_fn=_machine,
        checkpoint_callback=snapshots.append,
        limit=1,
    )
    assert len(snapshots) == 1
    assert snapshots[0].evidence_state == "GENERATED_MIGRATION_CAMPAIGN_INCOMPLETE_OR_FAILED"
    assert campaign.evidence_state == "GENERATED_MIGRATION_CAMPAIGN_INCOMPLETE_OR_FAILED"
