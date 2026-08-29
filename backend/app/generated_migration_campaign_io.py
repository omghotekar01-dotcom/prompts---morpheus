from __future__ import annotations

from typing import Any, Mapping

from .generated_migration_benchmark import GeneratedMigrationBenchmarkReport, MigrationBenchmarkConfig, MigrationBenchmarkRow
from .generated_migration_campaign import GeneratedMigrationCampaignEntry, GeneratedMigrationCampaignReport
from .generated_migration_release_evidence import validate_generated_migration_campaign_payload


def _report_from_payload(payload: Mapping[str, Any]) -> GeneratedMigrationBenchmarkReport:
    config_raw = payload["config"]
    rows_raw = payload["rows"]
    assert isinstance(config_raw, Mapping)
    assert isinstance(rows_raw, list)
    config = MigrationBenchmarkConfig(
        readers=int(config_raw["readers"]),
        transitions=int(config_raw["transitions"]),
        repetitions=int(config_raw["repetitions"]),
        record_count=int(config_raw["record_count"]),
    )
    rows = tuple(
        MigrationBenchmarkRow(
            repetition=int(row["repetition"]),
            readers=int(row["readers"]),
            transitions=int(row["transitions"]),
            record_count=int(row["record_count"]),
            migrate_validate_activate_ns_per=int(row["migrate_validate_activate_ns_per"]),
            rollback_ns_per=int(row["rollback_ns_per"]),
            reads=int(row["reads"]),
            invalid_reads=int(row["invalid_reads"]),
        )
        for row in rows_raw
    )
    return GeneratedMigrationBenchmarkReport(
        success=payload.get("success") is True,
        evidence_state=str(payload["evidence_state"]),
        source_candidate_id=str(payload["source_candidate_id"]),
        target_candidate_id=str(payload["target_candidate_id"]),
        workload_ir_hash=str(payload["workload_ir_hash"]),
        source_configuration_ir_hash=str(payload["source_configuration_ir_hash"]),
        target_configuration_ir_hash=str(payload["target_configuration_ir_hash"]),
        source_manifest_sha256=str(payload["source_manifest_sha256"]),
        target_manifest_sha256=str(payload["target_manifest_sha256"]),
        source_header_sha256=str(payload["source_header_sha256"]),
        target_header_sha256=str(payload["target_header_sha256"]),
        benchmark_source_sha256=str(payload["benchmark_source_sha256"]),
        compiler=str(payload["compiler"]) if payload.get("compiler") is not None else None,
        compiler_kind=str(payload["compiler_kind"]) if payload.get("compiler_kind") is not None else None,
        compiler_version=str(payload["compiler_version"]) if payload.get("compiler_version") is not None else None,
        config=config,
        rows=rows,
        compile_returncode=int(payload["compile_returncode"]) if payload.get("compile_returncode") is not None else None,
        run_returncode=int(payload["run_returncode"]) if payload.get("run_returncode") is not None else None,
        compile_stdout=str(payload.get("compile_stdout", "")),
        compile_stderr=str(payload.get("compile_stderr", "")),
        run_stdout=str(payload.get("run_stdout", "")),
        run_stderr=str(payload.get("run_stderr", "")),
    )


def load_generated_migration_campaign(payload: Mapping[str, Any]) -> GeneratedMigrationCampaignReport:
    """Validate then reconstruct a persisted RQ7 campaign without executing benchmarks."""

    validate_generated_migration_campaign_payload(payload)
    raw_entries = payload["entries"]
    machine_profile = payload["machine_profile"]
    assert isinstance(raw_entries, list)
    assert isinstance(machine_profile, Mapping)

    entries: list[GeneratedMigrationCampaignEntry] = []
    for raw in raw_entries:
        assert isinstance(raw, Mapping)
        factors = raw["factors"]
        report_payload = raw["report"]
        assert isinstance(factors, Mapping)
        assert isinstance(report_payload, Mapping)
        entries.append(
            GeneratedMigrationCampaignEntry(
                experiment_id=str(raw["experiment_id"]),
                factor_sha256=str(raw["factor_sha256"]),
                factors=dict(factors),
                report_sha256=str(raw["report_sha256"]),
                report=_report_from_payload(report_payload),
                verified_total_reads=(
                    int(raw["verified_total_reads"])
                    if raw.get("verified_total_reads") is not None
                    else None
                ),
            )
        )

    return GeneratedMigrationCampaignReport(
        schema=str(payload["schema"]),
        study_id=str(payload["study_id"]),
        manifest_sha256=str(payload["manifest_sha256"]),
        source_candidate_id=str(payload["source_candidate_id"]),
        target_candidate_id=str(payload["target_candidate_id"]),
        source_manifest_sha256=str(payload["source_manifest_sha256"]),
        target_manifest_sha256=str(payload["target_manifest_sha256"]),
        machine_profile_sha256=str(payload["machine_profile_sha256"]),
        machine_fingerprint_sha256=str(payload["machine_fingerprint_sha256"]),
        machine_profile=dict(machine_profile),
        planned_experiments=int(payload["planned_experiments"]),
        executed_experiments=int(payload["executed_experiments"]),
        entries=tuple(entries),
        complete=payload.get("complete") is True,
        comparable_environment=payload.get("comparable_environment") is True,
        evidence_state=str(payload["evidence_state"]),
        campaign_sha256=str(payload["campaign_sha256"]),
    )
