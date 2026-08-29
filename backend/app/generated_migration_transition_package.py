from __future__ import annotations

from typing import Any, Mapping


def validate_generated_migration_transition_package_links(
    artifacts: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Cross-link the complete-local transition attestation to packaged RQ7 evidence."""

    errors: list[str] = []
    attestation_item = artifacts.get("generated_migration_transition_cost_evidence")
    if not isinstance(attestation_item, Mapping):
        return errors
    attestation = attestation_item.get("json")
    if not isinstance(attestation, Mapping):
        return ["generated migration transition-cost evidence must be packaged as JSON"]

    campaign_item = artifacts.get("generated_migration_campaign")
    summary_item = artifacts.get("generated_migration_campaign_summary")
    machine_item = artifacts.get("machine_profile")
    experiment_item = artifacts.get("experiment_manifest")

    campaign = campaign_item.get("json") if isinstance(campaign_item, Mapping) else None
    summary = summary_item.get("json") if isinstance(summary_item, Mapping) else None
    machine = machine_item.get("json") if isinstance(machine_item, Mapping) else None
    experiment = experiment_item.get("json") if isinstance(experiment_item, Mapping) else None

    required = {
        "generated_migration_campaign": campaign,
        "generated_migration_campaign_summary": summary,
        "machine_profile": machine,
        "experiment_manifest": experiment,
    }
    for role, payload in required.items():
        if not isinstance(payload, Mapping):
            errors.append(f"generated migration transition-cost evidence requires packaged {role}")
    if errors:
        return errors

    assert isinstance(campaign, Mapping)
    assert isinstance(summary, Mapping)
    assert isinstance(machine, Mapping)
    assert isinstance(experiment, Mapping)

    direct_links = {
        "manifest_sha256": experiment.get("manifest_sha256"),
        "campaign_sha256": campaign.get("campaign_sha256"),
        "machine_profile_sha256": campaign.get("machine_profile_sha256"),
        "machine_fingerprint_sha256": machine.get("machine_fingerprint_sha256"),
        "source_candidate_id": campaign.get("source_candidate_id"),
        "target_candidate_id": campaign.get("target_candidate_id"),
        "source_manifest_sha256": campaign.get("source_manifest_sha256"),
        "target_manifest_sha256": campaign.get("target_manifest_sha256"),
        "experiment_count": campaign.get("planned_experiments"),
    }
    for field, expected in direct_links.items():
        if attestation.get(field) != expected:
            errors.append(f"generated migration transition-cost evidence {field} does not match packaged RQ7 evidence")

    summary_hash = summary_item.get("canonical_json_sha256") if isinstance(summary_item, Mapping) else None
    if summary_hash and attestation.get("summary_sha256") != summary_hash:
        errors.append("generated migration transition-cost evidence summary_sha256 does not match packaged summary canonical hash")

    machine_hash = machine_item.get("canonical_json_sha256") if isinstance(machine_item, Mapping) else None
    if machine_hash and attestation.get("machine_profile_sha256") != machine_hash:
        errors.append("generated migration transition-cost evidence machine_profile_sha256 does not match packaged machine profile canonical hash")

    if campaign.get("evidence_state") != "GENERATED_MIGRATION_CAMPAIGN_COMPLETE_LOCAL_MEASUREMENTS":
        errors.append("generated migration transition-cost evidence requires a complete local-measurement campaign")
    if campaign.get("complete") is not True or campaign.get("comparable_environment") is not True:
        errors.append("generated migration transition-cost evidence requires complete=true and comparable_environment=true")
    if summary.get("successful_experiments") != campaign.get("planned_experiments"):
        errors.append("generated migration transition-cost evidence requires summary coverage of every frozen experiment")
    if experiment.get("study_id") != "rq7-generated-migration-v1":
        errors.append("generated migration transition-cost evidence requires RQ7 experiment manifest")

    return errors
