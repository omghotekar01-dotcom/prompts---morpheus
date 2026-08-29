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

    return errors
