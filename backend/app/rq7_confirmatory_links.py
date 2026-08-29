from __future__ import annotations

from typing import Any, Mapping


def validate_rq7_confirmatory_cross_links(artifacts: Mapping[str, Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    analysis_item = artifacts.get("rq7_confirmatory_analysis")
    if not isinstance(analysis_item, Mapping):
        return errors
    analysis = analysis_item.get("json")
    if not isinstance(analysis, Mapping):
        return errors

    campaign_item = artifacts.get("generated_migration_campaign")
    campaign = campaign_item.get("json") if isinstance(campaign_item, Mapping) else None
    if isinstance(campaign, Mapping):
        for field in (
            "manifest_sha256",
            "campaign_sha256",
            "machine_profile_sha256",
            "machine_fingerprint_sha256",
            "source_candidate_id",
            "target_candidate_id",
        ):
            if analysis.get(field) != campaign.get(field):
                errors.append(f"RQ7 confirmatory analysis {field} does not match generated migration campaign")
        if campaign.get("evidence_state") != "GENERATED_MIGRATION_CAMPAIGN_COMPLETE_LOCAL_MEASUREMENTS":
            errors.append("RQ7 confirmatory analysis requires a complete non-CI local generated migration campaign")
        if campaign.get("complete") is not True or campaign.get("comparable_environment") is not True:
            errors.append("RQ7 confirmatory analysis campaign must be complete and comparable")

    experiment_item = artifacts.get("experiment_manifest")
    experiment = experiment_item.get("json") if isinstance(experiment_item, Mapping) else None
    if isinstance(experiment, Mapping):
        if analysis.get("manifest_sha256") != experiment.get("manifest_sha256"):
            errors.append("RQ7 confirmatory analysis manifest_sha256 does not match packaged experiment manifest")
        if experiment.get("study_id") != "rq7-generated-migration-v1":
            errors.append("RQ7 confirmatory analysis requires the packaged RQ7 v1 experiment manifest")
        experiments = experiment.get("experiments")
        if not isinstance(experiments, list) or len(experiments) != 24:
            errors.append("RQ7 confirmatory analysis requires the complete 24-cell experiment manifest")

    machine_item = artifacts.get("machine_profile")
    machine = machine_item.get("json") if isinstance(machine_item, Mapping) else None
    if isinstance(machine, Mapping):
        canonical = str(machine_item.get("canonical_json_sha256", ""))
        if canonical and analysis.get("machine_profile_sha256") != canonical:
            errors.append("RQ7 confirmatory analysis machine_profile_sha256 does not match packaged machine profile")
        if analysis.get("machine_fingerprint_sha256") != machine.get("machine_fingerprint_sha256"):
            errors.append("RQ7 confirmatory analysis machine fingerprint does not match packaged machine profile")

    transition_item = artifacts.get("generated_migration_transition_cost_evidence")
    transition = transition_item.get("json") if isinstance(transition_item, Mapping) else None
    if isinstance(transition, Mapping):
        for field in (
            "manifest_sha256",
            "campaign_sha256",
            "machine_profile_sha256",
            "machine_fingerprint_sha256",
            "source_candidate_id",
            "target_candidate_id",
        ):
            if analysis.get(field) != transition.get(field):
                errors.append(f"RQ7 confirmatory analysis {field} does not match transition-cost attestation")
        if transition.get("evidence_state") != "COMPLETE_LOCAL_RQ7_GENERATED_MIGRATION_TRANSITION_COST_EVIDENCE":
            errors.append("RQ7 confirmatory analysis requires the complete-local transition-cost attestation")

    environment_item = artifacts.get("measurement_environment_record")
    environment = environment_item.get("json") if isinstance(environment_item, Mapping) else None
    if isinstance(environment, Mapping):
        if analysis.get("campaign_sha256") != environment.get("campaign_sha256"):
            errors.append("RQ7 confirmatory analysis campaign_sha256 does not match measurement environment record")
        if analysis.get("machine_fingerprint_sha256") != environment.get("machine_fingerprint_sha256"):
            errors.append("RQ7 confirmatory analysis machine fingerprint does not match measurement environment record")
        if environment.get("evidence_state") != "LOCAL_MEASUREMENT_ENVIRONMENT_METADATA_CAPTURED_NOT_CONTROL_PROOF":
            errors.append("RQ7 confirmatory claim requires non-CI local measurement environment metadata")

        coverage = environment.get("coverage")
        if not isinstance(coverage, Mapping):
            errors.append("RQ7 confirmatory claim requires explicit measurement environment coverage")
        else:
            if coverage.get("complete_single_invocation_coverage") is not True:
                errors.append("RQ7 confirmatory claim requires complete single-invocation environment coverage")
            if coverage.get("resumed_from_campaign_sha256") is not None:
                errors.append("RQ7 confirmatory claim does not accept a resumed multi-invocation environment record")
            covered = coverage.get("covered_experiment_ids")
            raw_cells = analysis.get("raw_cells")
            expected_ids = (
                {
                    str(cell.get("experiment_id", ""))
                    for cell in raw_cells
                    if isinstance(cell, Mapping)
                }
                if isinstance(raw_cells, list)
                else set()
            )
            actual_ids = (
                set(covered)
                if isinstance(covered, list) and all(isinstance(item, str) for item in covered)
                else set()
            )
            if actual_ids != expected_ids or len(actual_ids) != 24:
                errors.append("RQ7 measurement environment coverage does not match all 24 analyzed experiment ids")

        start = environment.get("start_snapshot")
        end = environment.get("end_snapshot")
        stability = environment.get("observed_stability")
        if not isinstance(start, Mapping) or not isinstance(end, Mapping) or not isinstance(stability, Mapping):
            errors.append("RQ7 confirmatory claim requires start/end environment snapshots and observed stability")
        else:
            if stability.get("same_logical_cpu_count") is not True:
                errors.append("RQ7 confirmatory claim requires a stable observed logical CPU count")
            if stability.get("process_affinity_stable") is not True:
                errors.append("RQ7 confirmatory claim requires observable stable process affinity")
            power_policy_observed = bool(start.get("linux_scaling_governors")) or start.get("windows_active_power_scheme") is not None
            power_policy_stable = (
                stability.get("linux_governors_stable") is True
                or stability.get("windows_power_scheme_stable") is True
            )
            if not power_policy_observed or not power_policy_stable:
                errors.append("RQ7 confirmatory claim requires an observable stable CPU governor or Windows power scheme")

            if isinstance(machine, Mapping):
                machine_platform = machine.get("platform")
                machine_cpu = machine.get("cpu")
                expected_system = machine_platform.get("system") if isinstance(machine_platform, Mapping) else None
                expected_logical = machine_cpu.get("logical_count") if isinstance(machine_cpu, Mapping) else None
                if start.get("platform") != expected_system or end.get("platform") != expected_system:
                    errors.append("RQ7 measurement environment platform does not match packaged machine profile")
                if start.get("logical_cpu_count") != expected_logical or end.get("logical_cpu_count") != expected_logical:
                    errors.append("RQ7 measurement environment logical CPU count does not match packaged machine profile")

    return errors
