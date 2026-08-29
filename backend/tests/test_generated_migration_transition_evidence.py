from __future__ import annotations

import json
from dataclasses import replace

import pytest

from app.generated_migration_benchmark import (
    GeneratedMigrationBenchmarkReport,
    MigrationBenchmarkConfig,
    MigrationBenchmarkRow,
)
from app.generated_migration_campaign import (
    GeneratedMigrationCampaignEntry,
    GeneratedMigrationCampaignReport,
    summarize_generated_migration_campaign,
)
from app.generated_migration_transition_evidence import (
    build_generated_migration_transition_cost_evidence,
    canonical_transition_cost_evidence_bytes,
    validate_generated_migration_transition_cost_evidence_bytes,
)
from app.generated_migration_transition_package import validate_generated_migration_transition_package_links
from app.machine_profile import machine_identity_document, machine_profile_fingerprint
from app.release_evidence_validation import validate_release_evidence_bytes


def _machine() -> dict[str, object]:
    profile: dict[str, object] = {
        "schema_version": 2,
        "protocol": "morpheus-machine-profile-v2",
        "captured_at": "2026-08-29T00:00:00+00:00",
        "source_commit": "a" * 40,
        "platform": {"system": "TestOS", "release": "1", "version": "1", "machine": "x86_64", "processor": "cpu", "python": "3.14"},
        "cpu": {"logical_count": 8, "linux": {}, "windows": {}},
        "toolchain": {"compiler": "/fake/g++", "compiler_kind": "gnu", "compiler_version": "fake 1", "cmake": None, "git": None},
        "environment": {"python_executable": "/fake/python", "temp": "/tmp"},
        "truth_note": "fixture",
    }
    profile["machine_fingerprint_sha256"] = machine_profile_fingerprint(profile)
    profile["machine_identity"] = machine_identity_document(profile)
    return profile


def _report(*, experiment: int, state: str = "MEASURED_LOCAL_PROCESS_GENERATED_MIGRATION_TRANSITION_COST") -> GeneratedMigrationBenchmarkReport:
    config = MigrationBenchmarkConfig(readers=4, transitions=10, repetitions=2, record_count=128 * (experiment + 1))
    rows = tuple(
        MigrationBenchmarkRow(
            repetition=repetition,
            readers=config.readers,
            transitions=config.transitions,
            record_count=config.record_count,
            migrate_validate_activate_ns_per=10000 + experiment * 1000 + repetition,
            rollback_ns_per=1000 + repetition,
            reads=500 + repetition,
            invalid_reads=0,
        )
        for repetition in range(config.repetitions)
    )
    return GeneratedMigrationBenchmarkReport(
        success=True,
        evidence_state=state,
        source_candidate_id="source-a",
        target_candidate_id="target-b",
        workload_ir_hash="1" * 64,
        source_configuration_ir_hash="2" * 64,
        target_configuration_ir_hash="3" * 64,
        source_manifest_sha256="4" * 64,
        target_manifest_sha256="5" * 64,
        source_header_sha256="6" * 64,
        target_header_sha256="7" * 64,
        benchmark_source_sha256="8" * 64,
        compiler="/fake/g++",
        compiler_kind="gnu",
        compiler_version="fake 1",
        config=config,
        rows=rows,
        compile_returncode=0,
        run_returncode=0,
    )


def _campaign(*, state: str = "GENERATED_MIGRATION_CAMPAIGN_COMPLETE_LOCAL_MEASUREMENTS", report_state: str = "MEASURED_LOCAL_PROCESS_GENERATED_MIGRATION_TRANSITION_COST") -> GeneratedMigrationCampaignReport:
    machine = _machine()
    entries = []
    for index in range(2):
        report = _report(experiment=index, state=report_state)
        entries.append(
            GeneratedMigrationCampaignEntry(
                experiment_id=f"mx-{index}",
                factor_sha256=str(index + 9) * 64,
                factors={
                    "candidate_pair_policy": "winner-to-best-distinct",
                    "readers": report.config.readers,
                    "record_count": report.config.record_count,
                    "transitions": report.config.transitions,
                    "workload_name": "users_demo",
                },
                report_sha256=str(index + 1) * 64,
                report=report,
                verified_total_reads=sum(row.reads for row in report.rows),
            )
        )
    machine_canonical = json.dumps(machine, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    import hashlib

    return GeneratedMigrationCampaignReport(
        schema="morpheus-generated-migration-campaign-v1",
        study_id="rq7-generated-migration-v1",
        manifest_sha256="a" * 64,
        source_candidate_id="source-a",
        target_candidate_id="target-b",
        source_manifest_sha256="4" * 64,
        target_manifest_sha256="5" * 64,
        machine_profile_sha256=hashlib.sha256(machine_canonical).hexdigest(),
        machine_fingerprint_sha256=str(machine["machine_fingerprint_sha256"]),
        machine_profile=machine,
        planned_experiments=2,
        executed_experiments=2,
        entries=tuple(entries),
        complete=True,
        comparable_environment=True,
        evidence_state=state,
        campaign_sha256="b" * 64,
    )


def test_complete_local_campaign_can_mint_transition_cost_attestation() -> None:
    campaign = _campaign()
    summary = summarize_generated_migration_campaign(campaign)
    attestation = build_generated_migration_transition_cost_evidence(campaign, summary=summary)
    result = validate_generated_migration_transition_cost_evidence_bytes(
        canonical_transition_cost_evidence_bytes(attestation)
    )
    assert result.valid is True
    assert attestation["invalid_reader_observations"] == 0
    assert attestation["total_timing_observations"] == 4
    assert attestation["claim_scope"] == "MEASURED_TRANSITION_COST_FOR_FROZEN_RQ7_MATRIX_ON_ONE_MACHINE"


def test_ci_smoke_and_partial_campaigns_cannot_mint_complete_local_attestation() -> None:
    ci_campaign = _campaign(
        state="GENERATED_MIGRATION_CAMPAIGN_COMPLETE_CI_SMOKE",
        report_state="MEASURED_CI_SMOKE_GENERATED_MIGRATION_TRANSITION_COST",
    )
    with pytest.raises(ValueError, match="non-CI local"):
        build_generated_migration_transition_cost_evidence(ci_campaign)

    partial = replace(
        _campaign(),
        complete=False,
        planned_experiments=3,
        evidence_state="GENERATED_MIGRATION_CAMPAIGN_PARTIAL_VERIFIED",
    )
    with pytest.raises(ValueError, match="complete RQ7"):
        build_generated_migration_transition_cost_evidence(partial)


def test_transition_attestation_hash_tampering_is_rejected() -> None:
    campaign = _campaign()
    attestation = build_generated_migration_transition_cost_evidence(campaign)
    attestation["campaign_sha256"] = "c" * 64
    result = validate_generated_migration_transition_cost_evidence_bytes(
        canonical_transition_cost_evidence_bytes(attestation)
    )
    assert result.valid is False
    assert any("attestation_sha256" in detail for detail in result.details)


def test_release_dispatch_accepts_valid_machine_profile_v2_and_rejects_tamper() -> None:
    machine = _machine()
    good = validate_release_evidence_bytes("machine_profile", json.dumps(machine).encode())
    assert good.valid is True
    machine["machine_fingerprint_sha256"] = "0" * 64
    bad = validate_release_evidence_bytes("machine_profile", json.dumps(machine).encode())
    assert bad.valid is False
    assert any("fingerprint" in detail for detail in bad.details)


def test_transition_package_cross_links_reject_swapped_summary_hash() -> None:
    campaign = _campaign()
    summary = summarize_generated_migration_campaign(campaign)
    attestation = build_generated_migration_transition_cost_evidence(campaign, summary=summary)
    machine = campaign.machine_profile
    summary_canonical = json.dumps(summary, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    machine_canonical = json.dumps(machine, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    import hashlib

    context = {
        "generated_migration_transition_cost_evidence": {"json": attestation},
        "generated_migration_campaign": {"json": campaign.as_dict()},
        "generated_migration_campaign_summary": {"json": summary, "canonical_json_sha256": hashlib.sha256(summary_canonical).hexdigest()},
        "machine_profile": {"json": machine, "canonical_json_sha256": hashlib.sha256(machine_canonical).hexdigest()},
        "experiment_manifest": {
            "json": {
                "schema": "morpheus-experiment-manifest-v1",
                "study_id": "rq7-generated-migration-v1",
                "manifest_sha256": campaign.manifest_sha256,
                "experiments": [{"experiment_id": "mx-0"}, {"experiment_id": "mx-1"}],
            }
        },
    }
    assert validate_generated_migration_transition_package_links(context) == []

    context["generated_migration_campaign_summary"]["canonical_json_sha256"] = "f" * 64
    errors = validate_generated_migration_transition_package_links(context)
    assert any("summary_sha256" in error for error in errors)
