from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .generated_migration_benchmark_evidence import verify_generated_migration_benchmark_evidence
from .machine_profile import MACHINE_PROFILE_PROTOCOL, machine_profile_fingerprint


CAMPAIGN_SCHEMA = "morpheus-generated-migration-campaign-v1"
SUMMARY_SCHEMA = "morpheus-generated-migration-campaign-summary-v1"
_ALLOWED_CAMPAIGN_STATES = {
    "GENERATED_MIGRATION_CAMPAIGN_PARTIAL_VERIFIED",
    "GENERATED_MIGRATION_CAMPAIGN_COMPLETE_CI_SMOKE",
    "GENERATED_MIGRATION_CAMPAIGN_COMPLETE_LOCAL_MEASUREMENTS",
    "GENERATED_MIGRATION_CAMPAIGN_COMPLETE_MIXED_ENVIRONMENT_NOT_COMPARABLE",
}


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _json_object(data: bytes) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"RQ7 evidence must be a UTF-8 JSON object: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("RQ7 evidence top-level value must be an object")
    return value


def validate_rq7_machine_profile(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != 2 or payload.get("protocol") != MACHINE_PROFILE_PROTOCOL:
        raise ValueError("RQ7 requires morpheus-machine-profile-v2 with schema_version=2")
    platform = payload.get("platform")
    cpu = payload.get("cpu")
    toolchain = payload.get("toolchain")
    if not isinstance(platform, Mapping) or not isinstance(cpu, Mapping) or not isinstance(toolchain, Mapping):
        raise ValueError("RQ7 machine profile requires platform, cpu and toolchain objects")
    if not str(toolchain.get("compiler") or "").strip():
        raise ValueError("RQ7 machine profile requires the selected compiler identity")
    if toolchain.get("compiler_kind") not in {"gnu", "msvc"}:
        raise ValueError("RQ7 machine profile has unsupported compiler_kind")
    if not str(toolchain.get("compiler_version") or "").strip():
        raise ValueError("RQ7 machine profile requires compiler_version")
    expected = machine_profile_fingerprint(dict(payload))
    if payload.get("machine_fingerprint_sha256") != expected:
        raise ValueError("RQ7 machine profile fingerprint does not match its stable identity")


def validate_generated_migration_campaign_payload(payload: Mapping[str, Any]) -> None:
    if payload.get("schema") != CAMPAIGN_SCHEMA:
        raise ValueError("unexpected generated migration campaign schema")
    if payload.get("study_id") != "rq7-generated-migration-v1":
        raise ValueError("generated migration campaign must be RQ7 v1")
    for field in (
        "manifest_sha256",
        "source_manifest_sha256",
        "target_manifest_sha256",
        "machine_profile_sha256",
        "machine_fingerprint_sha256",
        "campaign_sha256",
    ):
        if not _valid_sha256(payload.get(field)):
            raise ValueError(f"generated migration campaign has invalid {field}")
    source = str(payload.get("source_candidate_id", ""))
    target = str(payload.get("target_candidate_id", ""))
    if not source or not target or source == target:
        raise ValueError("generated migration campaign requires distinct source/target candidates")

    machine = payload.get("machine_profile")
    if not isinstance(machine, Mapping):
        raise ValueError("generated migration campaign must embed its machine profile")
    validate_rq7_machine_profile(machine)
    if _canonical_sha256(machine) != payload.get("machine_profile_sha256"):
        raise ValueError("generated migration campaign machine_profile_sha256 does not match embedded profile")
    if machine.get("machine_fingerprint_sha256") != payload.get("machine_fingerprint_sha256"):
        raise ValueError("generated migration campaign machine fingerprint differs from embedded profile")

    planned = payload.get("planned_experiments")
    executed = payload.get("executed_experiments")
    entries = payload.get("entries")
    if isinstance(planned, bool) or not isinstance(planned, int) or planned <= 0:
        raise ValueError("generated migration campaign planned_experiments must be positive")
    if isinstance(executed, bool) or not isinstance(executed, int) or executed < 0 or executed > planned:
        raise ValueError("generated migration campaign executed_experiments is invalid")
    if not isinstance(entries, list) or len(entries) != executed:
        raise ValueError("generated migration campaign entry count must equal executed_experiments")

    state = payload.get("evidence_state")
    if state not in _ALLOWED_CAMPAIGN_STATES:
        raise ValueError("generated migration campaign has unsupported evidence_state")
    complete = payload.get("complete") is True
    if complete != (executed == planned and entries and all(isinstance(item, Mapping) and item.get("report", {}).get("success") is True for item in entries)):
        raise ValueError("generated migration campaign complete flag is inconsistent with entries")
    if state.startswith("GENERATED_MIGRATION_CAMPAIGN_COMPLETE_") and not complete:
        raise ValueError("complete generated migration campaign state requires complete=true")
    if state == "GENERATED_MIGRATION_CAMPAIGN_PARTIAL_VERIFIED" and not (0 < executed < planned):
        raise ValueError("partial generated migration campaign state requires a strict experiment prefix")

    seen_experiments: set[str] = set()
    report_states: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise ValueError(f"generated migration campaign entries[{index}] must be an object")
        experiment_id = str(entry.get("experiment_id", ""))
        if not experiment_id or experiment_id in seen_experiments:
            raise ValueError("generated migration campaign experiment identities must be unique and non-empty")
        seen_experiments.add(experiment_id)
        if not _valid_sha256(entry.get("factor_sha256")) or not _valid_sha256(entry.get("report_sha256")):
            raise ValueError(f"generated migration campaign entries[{index}] has invalid factor/report hash")
        factors = entry.get("factors")
        report = entry.get("report")
        if not isinstance(factors, Mapping) or not isinstance(report, Mapping):
            raise ValueError(f"generated migration campaign entries[{index}] requires factors and report objects")
        if _canonical_sha256(factors) != entry.get("factor_sha256"):
            raise ValueError(f"generated migration campaign entries[{index}] factor hash mismatch")
        if _canonical_sha256(report) != entry.get("report_sha256"):
            raise ValueError(f"generated migration campaign entries[{index}] report hash mismatch")
        verified = verify_generated_migration_benchmark_evidence(report)
        if verified.source_candidate_id != source or verified.target_candidate_id != target:
            raise ValueError("generated migration campaign report candidate identity mismatch")
        if tuple(verified.manifest_hashes) != (
            payload.get("source_manifest_sha256"),
            payload.get("target_manifest_sha256"),
        ):
            raise ValueError("generated migration campaign report manifest identity mismatch")
        report_states.add(verified.evidence_state)
        if entry.get("verified_total_reads") != verified.total_reads:
            raise ValueError("generated migration campaign verified_total_reads mismatch")

        expected_factor_fields = {"candidate_pair_policy", "readers", "record_count", "transitions", "workload_name"}
        if set(factors) != expected_factor_fields:
            raise ValueError("generated migration campaign factor schema mismatch")
        config = report.get("config")
        if not isinstance(config, Mapping):
            raise ValueError("generated migration campaign report lacks config")
        if factors.get("readers") != config.get("readers") or factors.get("record_count") != config.get("record_count") or factors.get("transitions") != config.get("transitions"):
            raise ValueError("generated migration campaign factors do not match benchmark config")

        toolchain = machine.get("toolchain")
        assert isinstance(toolchain, Mapping)
        if (
            report.get("compiler"),
            report.get("compiler_kind"),
            report.get("compiler_version"),
        ) != (
            toolchain.get("compiler"),
            toolchain.get("compiler_kind"),
            toolchain.get("compiler_version"),
        ):
            raise ValueError("generated migration campaign report toolchain differs from machine profile")

    comparable = payload.get("comparable_environment") is True
    homogeneous = len(report_states) <= 1
    if comparable and not homogeneous:
        raise ValueError("generated migration campaign cannot be comparable across mixed evidence environments")
    if state == "GENERATED_MIGRATION_CAMPAIGN_COMPLETE_CI_SMOKE" and report_states != {"MEASURED_CI_SMOKE_GENERATED_MIGRATION_TRANSITION_COST"}:
        raise ValueError("CI-smoke campaign state requires only CI-smoke reports")
    if state == "GENERATED_MIGRATION_CAMPAIGN_COMPLETE_LOCAL_MEASUREMENTS" and report_states != {"MEASURED_LOCAL_PROCESS_GENERATED_MIGRATION_TRANSITION_COST"}:
        raise ValueError("local-measurement campaign state requires only local measurement reports")


def validate_generated_migration_summary_payload(payload: Mapping[str, Any]) -> None:
    if payload.get("schema") != SUMMARY_SCHEMA:
        raise ValueError("unexpected generated migration campaign summary schema")
    if payload.get("study_id") != "rq7-generated-migration-v1":
        raise ValueError("generated migration summary must be RQ7 v1")
    for field in ("manifest_sha256", "campaign_sha256", "machine_profile_sha256", "machine_fingerprint_sha256"):
        if not _valid_sha256(payload.get(field)):
            raise ValueError(f"generated migration summary has invalid {field}")
    if payload.get("evidence_state") != "DESCRIPTIVE_SUMMARY_OF_GENERATED_MIGRATION_CAMPAIGN":
        raise ValueError("generated migration summary has unexpected evidence_state")
    planned = payload.get("planned_experiments")
    executed = payload.get("executed_experiments")
    successful = payload.get("successful_experiments")
    groups = payload.get("groups")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (planned, executed, successful)):
        raise ValueError("generated migration summary experiment counts must be integers")
    if not (0 <= successful <= executed <= planned):
        raise ValueError("generated migration summary experiment counts are inconsistent")
    if not isinstance(groups, list) or len(groups) != successful:
        raise ValueError("generated migration summary group count must equal successful_experiments")
    for index, group in enumerate(groups):
        if not isinstance(group, Mapping):
            raise ValueError(f"generated migration summary groups[{index}] must be an object")
        if group.get("invalid_reader_observations") != 0:
            raise ValueError("generated migration summary cannot report invalid reader observations")
        for metric in ("migrate_validate_activate_ns_per", "rollback_ns_per", "round_trip_transition_ns_per"):
            stats = group.get(metric)
            if not isinstance(stats, Mapping) or not isinstance(stats.get("n"), int) or stats.get("n", 0) <= 0:
                raise ValueError(f"generated migration summary groups[{index}] has invalid {metric}")
            for name in ("mean", "median", "stdev", "min", "p95", "p99", "max"):
                value = stats.get(name)
                if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
                    raise ValueError(f"generated migration summary groups[{index}] has invalid {metric}.{name}")
            if not stats["min"] <= stats["median"] <= stats["p95"] <= stats["p99"] <= stats["max"]:
                raise ValueError(f"generated migration summary groups[{index}] quantiles are inconsistent")


def validate_generated_migration_evidence_bytes(role: str, data: bytes) -> tuple[dict[str, Any], tuple[str, ...]]:
    payload = _json_object(data)
    if role == "machine_profile":
        validate_rq7_machine_profile(payload)
        return payload, ("validated morpheus-machine-profile-v2 identity and fingerprint",)
    if role == "generated_migration_campaign":
        validate_generated_migration_campaign_payload(payload)
        return payload, ("validated RQ7 campaign identities, report hashes, reader invariants and machine/toolchain binding",)
    if role == "generated_migration_campaign_summary":
        validate_generated_migration_summary_payload(payload)
        return payload, ("validated RQ7 descriptive summary structure and reader/timing invariants",)
    raise ValueError(f"unsupported RQ7 evidence role: {role}")


def validate_generated_migration_cross_links(artifacts: Mapping[str, Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    campaign_item = artifacts.get("generated_migration_campaign")
    summary_item = artifacts.get("generated_migration_campaign_summary")
    machine_item = artifacts.get("machine_profile")
    experiment_item = artifacts.get("experiment_manifest")

    campaign = campaign_item.get("json") if isinstance(campaign_item, Mapping) else None
    summary = summary_item.get("json") if isinstance(summary_item, Mapping) else None
    machine = machine_item.get("json") if isinstance(machine_item, Mapping) else None
    experiment = experiment_item.get("json") if isinstance(experiment_item, Mapping) else None

    if isinstance(campaign, Mapping) and isinstance(summary, Mapping):
        for field in ("manifest_sha256", "campaign_sha256", "machine_profile_sha256", "machine_fingerprint_sha256"):
            if campaign.get(field) != summary.get(field):
                errors.append(f"generated migration summary {field} does not match campaign")
        if campaign.get("planned_experiments") != summary.get("planned_experiments") or campaign.get("executed_experiments") != summary.get("executed_experiments"):
            errors.append("generated migration summary experiment counts do not match campaign")

    if isinstance(campaign, Mapping) and isinstance(machine, Mapping):
        canonical = str(machine_item.get("canonical_json_sha256", ""))
        if canonical and campaign.get("machine_profile_sha256") != canonical:
            errors.append("generated migration campaign machine_profile_sha256 does not match packaged machine profile canonical hash")
        if campaign.get("machine_fingerprint_sha256") != machine.get("machine_fingerprint_sha256"):
            errors.append("generated migration campaign machine fingerprint does not match packaged machine profile")

    if isinstance(campaign, Mapping) and isinstance(experiment, Mapping):
        if campaign.get("manifest_sha256") != experiment.get("manifest_sha256"):
            errors.append("generated migration campaign manifest_sha256 does not match packaged experiment manifest")
        if experiment.get("study_id") != "rq7-generated-migration-v1":
            errors.append("generated migration campaign requires packaged RQ7 experiment manifest")
        experiment_ids = {
            str(item.get("experiment_id", ""))
            for item in experiment.get("experiments", [])
            if isinstance(item, Mapping)
        }
        campaign_ids = [
            str(item.get("experiment_id", ""))
            for item in campaign.get("entries", [])
            if isinstance(item, Mapping)
        ]
        if any(item not in experiment_ids for item in campaign_ids):
            errors.append("generated migration campaign contains experiment ids absent from packaged experiment manifest")

    return errors
