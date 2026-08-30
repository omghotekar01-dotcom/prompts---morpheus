from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Mapping, Sequence

from .generated_migration_benchmark import (
    GeneratedMigrationBenchmarkReport,
    MigrationBenchmarkConfig,
    MigrationBenchmarkRow,
)
from .generated_migration_benchmark_evidence import verify_generated_migration_benchmark_evidence
from .research_suite import FrozenExperiment


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _report_from_payload(payload: Mapping[str, Any]) -> GeneratedMigrationBenchmarkReport:
    config_raw = payload.get("config")
    rows_raw = payload.get("rows")
    if not isinstance(config_raw, Mapping) or not isinstance(rows_raw, list):
        raise ValueError("resume benchmark report requires config object and rows array")
    config = MigrationBenchmarkConfig(
        readers=int(config_raw["readers"]),
        transitions=int(config_raw["transitions"]),
        repetitions=int(config_raw["repetitions"]),
        record_count=int(config_raw["record_count"]),
    )
    config.validate()
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
        if isinstance(row, Mapping)
    )
    if len(rows) != len(rows_raw):
        raise ValueError("resume benchmark report rows must all be objects")
    return GeneratedMigrationBenchmarkReport(
        success=payload.get("success") is True,
        evidence_state=str(payload.get("evidence_state", "")),
        source_candidate_id=str(payload.get("source_candidate_id", "")),
        target_candidate_id=str(payload.get("target_candidate_id", "")),
        workload_ir_hash=str(payload.get("workload_ir_hash", "")),
        source_configuration_ir_hash=str(payload.get("source_configuration_ir_hash", "")),
        target_configuration_ir_hash=str(payload.get("target_configuration_ir_hash", "")),
        source_manifest_sha256=str(payload.get("source_manifest_sha256", "")),
        target_manifest_sha256=str(payload.get("target_manifest_sha256", "")),
        source_header_sha256=str(payload.get("source_header_sha256", "")),
        target_header_sha256=str(payload.get("target_header_sha256", "")),
        benchmark_source_sha256=str(payload.get("benchmark_source_sha256", "")),
        compiler=str(payload.get("compiler")) if payload.get("compiler") is not None else None,
        compiler_kind=str(payload.get("compiler_kind")) if payload.get("compiler_kind") is not None else None,
        compiler_version=str(payload.get("compiler_version")) if payload.get("compiler_version") is not None else None,
        config=config,
        rows=rows,
        compile_returncode=payload.get("compile_returncode") if isinstance(payload.get("compile_returncode"), int) else None,
        run_returncode=payload.get("run_returncode") if isinstance(payload.get("run_returncode"), int) else None,
        compile_stdout=str(payload.get("compile_stdout", "")),
        compile_stderr=str(payload.get("compile_stderr", "")),
        run_stdout=str(payload.get("run_stdout", "")),
        run_stderr=str(payload.get("run_stderr", "")),
    )


def _verify_campaign_hash(payload: Mapping[str, Any], entries: Sequence[Mapping[str, Any]]) -> None:
    machine_profile_sha = payload.get("machine_profile_sha256")
    if not _valid_sha256(machine_profile_sha):
        raise ValueError("resume checkpoint lacks a valid machine_profile_sha256")
    embedded_profile = payload.get("machine_profile")
    if not isinstance(embedded_profile, Mapping):
        raise ValueError("resume checkpoint lacks embedded machine_profile object")
    if _canonical_sha256(embedded_profile) != machine_profile_sha:
        raise ValueError("resume checkpoint embedded machine profile hash mismatch")

    compact_entries: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise ValueError(f"resume checkpoint entries[{index}] must be an object")
        compact_entries.append(
            {
                "experiment_id": entry.get("experiment_id"),
                "factor_sha256": entry.get("factor_sha256"),
                "report_sha256": entry.get("report_sha256"),
            }
        )

    hash_core = {
        "schema": payload.get("schema"),
        "study_id": payload.get("study_id"),
        "manifest_sha256": payload.get("manifest_sha256"),
        "source_candidate_id": payload.get("source_candidate_id"),
        "target_candidate_id": payload.get("target_candidate_id"),
        "source_manifest_sha256": payload.get("source_manifest_sha256"),
        "target_manifest_sha256": payload.get("target_manifest_sha256"),
        "machine_profile_sha256": machine_profile_sha,
        "machine_fingerprint_sha256": payload.get("machine_fingerprint_sha256"),
        "entries": compact_entries,
    }
    expected_campaign_sha = _canonical_sha256(hash_core)
    if payload.get("campaign_sha256") != expected_campaign_sha:
        raise ValueError("resume checkpoint campaign hash mismatch")


def validate_rq7_resume_checkpoint(
    payload: Mapping[str, Any],
    *,
    manifest_sha256: str,
    machine_fingerprint_sha256: str,
    source_candidate_id: str,
    target_candidate_id: str,
    source_manifest_sha256: str,
    target_manifest_sha256: str,
    experiments: Sequence[FrozenExperiment],
    machine_profile: Mapping[str, Any],
) -> dict[str, GeneratedMigrationBenchmarkReport]:
    """Return verified reusable successful reports from one prior campaign.

    Failed prior cells are never silently retried through resume. The caller must
    preserve that failed campaign and explicitly start a new campaign if a retry
    policy is desired.
    """

    if payload.get("schema") != "morpheus-generated-migration-campaign-v1":
        raise ValueError("resume checkpoint has unexpected campaign schema")
    if payload.get("study_id") != "rq7-generated-migration-v1":
        raise ValueError("resume checkpoint is not RQ7 v1")
    if payload.get("manifest_sha256") != manifest_sha256:
        raise ValueError("resume checkpoint experiment manifest does not match current frozen matrix")
    if payload.get("machine_fingerprint_sha256") != machine_fingerprint_sha256:
        raise ValueError("resume checkpoint machine fingerprint differs from current machine")
    expected_identity = (
        source_candidate_id,
        target_candidate_id,
        source_manifest_sha256,
        target_manifest_sha256,
    )
    actual_identity = (
        payload.get("source_candidate_id"),
        payload.get("target_candidate_id"),
        payload.get("source_manifest_sha256"),
        payload.get("target_manifest_sha256"),
    )
    if actual_identity != expected_identity:
        raise ValueError("resume checkpoint generated candidate identity differs from current synthesis")

    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("resume checkpoint entries must be an array")
    _verify_campaign_hash(payload, entries)

    # Reject structurally ambiguous checkpoints before report/environment validation.
    # This makes malformed-identity errors deterministic across CI and local runs.
    experiment_ids = [str(entry.get("experiment_id", "")) for entry in entries if isinstance(entry, Mapping)]
    if len(experiment_ids) != len(entries):
        raise ValueError("resume checkpoint entries must all be objects")
    if len(set(experiment_ids)) != len(experiment_ids):
        raise ValueError("resume checkpoint contains duplicate experiment ids")

    by_experiment = {experiment.experiment_id: experiment for experiment in experiments}
    expected_environment_state = (
        "MEASURED_CI_SMOKE_GENERATED_MIGRATION_TRANSITION_COST"
        if os.environ.get("GITHUB_ACTIONS") == "true"
        else "MEASURED_LOCAL_PROCESS_GENERATED_MIGRATION_TRANSITION_COST"
    )
    toolchain = machine_profile.get("toolchain")
    if not isinstance(toolchain, Mapping):
        raise ValueError("current machine profile lacks toolchain identity")
    expected_toolchain = (
        toolchain.get("compiler"),
        toolchain.get("compiler_kind"),
        toolchain.get("compiler_version"),
    )

    reusable: dict[str, GeneratedMigrationBenchmarkReport] = {}
    for index, entry in enumerate(entries):
        assert isinstance(entry, Mapping)
        experiment_id = str(entry.get("experiment_id", ""))
        experiment = by_experiment.get(experiment_id)
        if experiment is None:
            raise ValueError(f"resume checkpoint contains unknown experiment id {experiment_id!r}")
        if entry.get("factor_sha256") != experiment.factor_sha256:
            raise ValueError(f"resume checkpoint factor hash mismatch for {experiment_id}")
        if entry.get("factors") != experiment.factors:
            raise ValueError(f"resume checkpoint factors differ from frozen experiment {experiment_id}")
        report_payload = entry.get("report")
        if not isinstance(report_payload, Mapping):
            raise ValueError(f"resume checkpoint {experiment_id} lacks report object")
        if entry.get("report_sha256") != _canonical_sha256(report_payload):
            raise ValueError(f"resume checkpoint report hash mismatch for {experiment_id}")
        if report_payload.get("success") is not True:
            raise ValueError(
                f"resume checkpoint contains failed experiment {experiment_id}; failed samples are never silently replaced"
            )
        verified = verify_generated_migration_benchmark_evidence(report_payload)
        if verified.evidence_state != expected_environment_state:
            raise ValueError("resume checkpoint measurement environment differs from current execution environment")
        if (
            verified.source_candidate_id,
            verified.target_candidate_id,
            tuple(verified.manifest_hashes),
        ) != (
            source_candidate_id,
            target_candidate_id,
            (source_manifest_sha256, target_manifest_sha256),
        ):
            raise ValueError(f"resume checkpoint report provenance mismatch for {experiment_id}")
        actual_toolchain = (
            report_payload.get("compiler"),
            report_payload.get("compiler_kind"),
            report_payload.get("compiler_version"),
        )
        if actual_toolchain != expected_toolchain:
            raise ValueError("resume checkpoint compiler identity differs from current machine profile")

        report = _report_from_payload(report_payload)
        expected_config = MigrationBenchmarkConfig(
            readers=int(experiment.factors["readers"]),
            transitions=int(experiment.factors["transitions"]),
            repetitions=int(experiment.repetitions),
            record_count=int(experiment.factors["record_count"]),
        )
        if report.config != expected_config:
            raise ValueError(f"resume checkpoint benchmark config differs from frozen experiment {experiment_id}")
        if entry.get("verified_total_reads") != verified.total_reads:
            raise ValueError(f"resume checkpoint verified_total_reads mismatch for {experiment_id}")
        reusable[experiment_id] = report

    return reusable
