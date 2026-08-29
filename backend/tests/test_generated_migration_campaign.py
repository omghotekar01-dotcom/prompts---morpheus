from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.artifact_manifest import artifact_manifest_hash
from app.generated_migration_benchmark import (
    GeneratedMigrationBenchmarkReport,
    MigrationBenchmarkRow,
)
from app.generated_migration_campaign import (
    freeze_generated_migration_campaign,
    run_generated_migration_campaign,
    summarize_generated_migration_campaign,
)
from app.machine_profile import machine_identity_document, machine_profile_fingerprint
from app.parser import parse_workload_text


REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = REPO_ROOT / "research" / "matrices" / "rq7-generated-migration.json"
EXAMPLE = REPO_ROOT / "examples" / "users-demo.yaml"


def _matrix() -> dict[str, object]:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def _fake_machine_profile() -> dict[str, object]:
    profile: dict[str, object] = {
        "schema_version": 2,
        "protocol": "morpheus-machine-profile-v2",
        "captured_at": "2026-08-29T00:00:00+00:00",
        "source_commit": "a" * 40,
        "platform": {
            "system": "TestOS",
            "release": "1",
            "version": "1",
            "machine": "x86_64",
            "processor": "test-cpu",
            "python": "3.14.0",
        },
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


def _success_report(bundle, config, *, ci: bool = False, compiler: str = "/fake/g++") -> GeneratedMigrationBenchmarkReport:
    rows = tuple(
        MigrationBenchmarkRow(
            repetition=index,
            readers=config.readers,
            transitions=config.transitions,
            record_count=config.record_count,
            migrate_validate_activate_ns_per=config.record_count * 10 + config.readers * 100 + index + 1,
            rollback_ns_per=1000 + config.readers * 10 + index + 1,
            reads=1000 + index,
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
        benchmark_source_sha256="b" * 64,
        compiler=compiler,
        compiler_kind="gnu",
        compiler_version="fake-g++ 1.0",
        config=config,
        rows=rows,
        compile_returncode=0,
        run_returncode=0,
    )


def _fake_success(bundle, spec, *, config, compile_timeout_seconds, run_timeout_seconds):
    assert spec.name == "users_demo"
    assert compile_timeout_seconds > 0
    assert run_timeout_seconds > 0
    return _success_report(bundle, config)


def _run(spec, *, benchmark_fn=_fake_success, resume_checkpoint=None, limit=None):
    return run_generated_migration_campaign(
        spec,
        _matrix(),
        benchmark_fn=benchmark_fn,
        machine_profile_fn=_fake_machine_profile,
        resume_checkpoint=resume_checkpoint,
        limit=limit,
    )


def test_rq7_campaign_freezes_to_expected_24_factor_combinations() -> None:
    manifest = freeze_generated_migration_campaign(_matrix())
    assert manifest.study_id == "rq7-generated-migration-v1"
    assert len(manifest.experiments) == 24
    assert manifest.seeds == (0,)
    assert all(item.repetitions == 10 for item in manifest.experiments)
    assert len({item.experiment_id for item in manifest.experiments}) == 24


def test_rq7_campaign_rejects_fake_randomized_seed_protocol() -> None:
    payload = _matrix()
    payload["seeds"] = [1337]
    with pytest.raises(ValueError, match="deterministic seed identity"):
        freeze_generated_migration_campaign(payload)


def test_generated_migration_campaign_executes_verified_reports_and_summarizes() -> None:
    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    campaign = _run(spec)
    assert campaign.complete is True
    assert campaign.comparable_environment is True
    assert campaign.executed_experiments == 24
    assert campaign.planned_experiments == 24
    assert campaign.evidence_state == "GENERATED_MIGRATION_CAMPAIGN_COMPLETE_LOCAL_MEASUREMENTS"
    assert campaign.source_candidate_id != campaign.target_candidate_id
    assert len(campaign.campaign_sha256) == 64
    assert len(campaign.machine_profile_sha256) == 64
    assert campaign.machine_fingerprint_sha256 == _fake_machine_profile()["machine_fingerprint_sha256"]
    assert all(entry.verified_total_reads is not None and entry.verified_total_reads > 0 for entry in campaign.entries)
    assert all(len(entry.report_sha256) == 64 for entry in campaign.entries)

    summary = summarize_generated_migration_campaign(campaign)
    assert summary["schema"] == "morpheus-generated-migration-campaign-summary-v1"
    assert summary["successful_experiments"] == 24
    assert summary["machine_profile_sha256"] == campaign.machine_profile_sha256
    assert len(summary["groups"]) == 24
    first = summary["groups"][0]
    assert first["invalid_reader_observations"] == 0
    assert first["migrate_validate_activate_ns_per"]["n"] == 10
    assert first["migrate_validate_activate_ns_per"]["p99"] >= first["migrate_validate_activate_ns_per"]["median"]
    assert first["round_trip_transition_ns_per"]["mean"] > first["rollback_ns_per"]["mean"]


def test_production_campaign_prepares_once_and_reuses_session(monkeypatch) -> None:
    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    counters = {"prepare": 0, "enter": 0, "run": 0, "exit": 0}

    class FakePrepared:
        def __init__(self, bundle):
            self.bundle = bundle

        def __enter__(self):
            counters["enter"] += 1
            return self

        def __exit__(self, exc_type, exc, traceback):
            counters["exit"] += 1

        def run(self, config, *, run_timeout_seconds):
            assert run_timeout_seconds == 120
            counters["run"] += 1
            return _success_report(self.bundle, config)

    def fake_prepare(bundle, spec_arg, *, compile_timeout_seconds):
        assert spec_arg.name == "users_demo"
        assert compile_timeout_seconds == 120
        counters["prepare"] += 1
        return FakePrepared(bundle)

    monkeypatch.setattr("app.generated_migration_campaign.prepare_generated_migration_benchmark", fake_prepare)
    campaign = run_generated_migration_campaign(
        spec,
        _matrix(),
        machine_profile_fn=_fake_machine_profile,
        limit=3,
    )
    assert campaign.executed_experiments == 3
    assert campaign.evidence_state == "GENERATED_MIGRATION_CAMPAIGN_PARTIAL_VERIFIED"
    assert counters == {"prepare": 1, "enter": 1, "run": 3, "exit": 1}


def test_resume_reuses_verified_cells_and_runs_only_missing_cells(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    prior = _run(spec, limit=2)
    calls = 0

    def counting_success(bundle, spec_arg, *, config, compile_timeout_seconds, run_timeout_seconds):
        nonlocal calls
        calls += 1
        return _success_report(bundle, config)

    resumed = _run(spec, benchmark_fn=counting_success, resume_checkpoint=prior.as_dict(), limit=4)
    assert calls == 2
    assert resumed.executed_experiments == 4
    assert [entry.experiment_id for entry in resumed.entries[:2]] == [entry.experiment_id for entry in prior.entries]
    assert [entry.report_sha256 for entry in resumed.entries[:2]] == [entry.report_sha256 for entry in prior.entries]


def test_resume_with_all_requested_cells_verified_executes_no_new_benchmark(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    prior = _run(spec, limit=2)

    def must_not_run(*args, **kwargs):
        raise AssertionError("verified resume cells must not execute a new benchmark")

    resumed = _run(spec, benchmark_fn=must_not_run, resume_checkpoint=prior.as_dict(), limit=2)
    assert resumed.executed_experiments == 2
    assert [entry.report_sha256 for entry in resumed.entries] == [entry.report_sha256 for entry in prior.entries]


def test_resume_tampering_aborts_before_any_new_measurement(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    prior = _run(spec, limit=1).as_dict()
    prior["entries"][0]["report"]["rows"][0]["invalid_reads"] = 1
    calls = 0

    def counting_success(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("tampered checkpoint must fail before benchmark execution")

    with pytest.raises(ValueError, match="report hash mismatch"):
        _run(spec, benchmark_fn=counting_success, resume_checkpoint=prior, limit=2)
    assert calls == 0


def test_generated_migration_campaign_limit_is_explicitly_partial() -> None:
    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))
    campaign = _run(spec, limit=2)
    assert campaign.complete is False
    assert campaign.executed_experiments == 2
    assert campaign.planned_experiments == 24
    assert campaign.evidence_state == "GENERATED_MIGRATION_CAMPAIGN_PARTIAL_VERIFIED"
    assert campaign.comparable_environment is True


def test_generated_migration_campaign_preserves_benchmark_failure() -> None:
    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))

    def fail(bundle, spec, *, config, compile_timeout_seconds, run_timeout_seconds):
        return GeneratedMigrationBenchmarkReport(
            success=False,
            evidence_state="COMPILER_UNAVAILABLE",
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
            compile_returncode=None,
            run_returncode=None,
        )

    campaign = _run(spec, benchmark_fn=fail, limit=1)
    assert campaign.complete is False
    assert campaign.comparable_environment is False
    assert campaign.evidence_state == "GENERATED_MIGRATION_CAMPAIGN_INCOMPLETE_OR_FAILED"
    assert campaign.entries[0].verified_total_reads is None
    summary = summarize_generated_migration_campaign(campaign)
    assert summary["successful_experiments"] == 0
    assert summary["groups"] == []


def test_generated_migration_campaign_rejects_compiler_identity_mismatch() -> None:
    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))

    def wrong_compiler(bundle, spec, *, config, compile_timeout_seconds, run_timeout_seconds):
        return _success_report(bundle, config, compiler="/different/clang++")

    with pytest.raises(ValueError, match="compiler identity differs"):
        _run(spec, benchmark_fn=wrong_compiler, limit=1)


def test_generated_migration_campaign_rejects_tampered_machine_fingerprint() -> None:
    spec = parse_workload_text(EXAMPLE.read_text(encoding="utf-8"))

    def tampered_profile():
        profile = _fake_machine_profile()
        profile["machine_fingerprint_sha256"] = "0" * 64
        return profile

    with pytest.raises(ValueError, match="fingerprint"):
        run_generated_migration_campaign(
            spec,
            _matrix(),
            benchmark_fn=_fake_success,
            machine_profile_fn=tampered_profile,
            limit=1,
        )
