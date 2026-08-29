from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .evidence_validation import EvidenceValidation
from .generated_migration_campaign import GeneratedMigrationCampaignReport, summarize_generated_migration_campaign


ROLE = "generated_migration_transition_cost_evidence"
SCHEMA = "morpheus-generated-migration-transition-cost-evidence-v1"
EVIDENCE_STATE = "COMPLETE_LOCAL_RQ7_GENERATED_MIGRATION_TRANSITION_COST_EVIDENCE"


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def build_generated_migration_transition_cost_evidence(
    campaign: GeneratedMigrationCampaignReport,
    *,
    summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Mint a narrow measurement attestation only from a complete local RQ7 run.

    This attests that the full frozen matrix was executed successfully on one
    machine/toolchain identity with zero invalid-reader observations. It does not
    attest superiority, causal scaling, production behavior, or cross-machine
    generalization. CI-smoke campaigns are intentionally ineligible.
    """

    if not campaign.complete:
        raise ValueError("transition-cost evidence requires a complete RQ7 campaign")
    if not campaign.comparable_environment:
        raise ValueError("transition-cost evidence requires one comparable measurement environment")
    if campaign.evidence_state != "GENERATED_MIGRATION_CAMPAIGN_COMPLETE_LOCAL_MEASUREMENTS":
        raise ValueError("transition-cost evidence requires complete non-CI local measurements")
    if not campaign.entries or any(
        entry.report.evidence_state != "MEASURED_LOCAL_PROCESS_GENERATED_MIGRATION_TRANSITION_COST"
        for entry in campaign.entries
    ):
        raise ValueError("transition-cost evidence cannot include CI-smoke or mixed-environment reports")
    if any(row.invalid_reads != 0 for entry in campaign.entries for row in entry.report.rows):
        raise ValueError("transition-cost evidence requires zero invalid reader observations")

    resolved_summary = dict(summary) if summary is not None else summarize_generated_migration_campaign(campaign)
    if resolved_summary.get("campaign_sha256") != campaign.campaign_sha256:
        raise ValueError("transition-cost summary is not bound to the supplied campaign")
    if resolved_summary.get("manifest_sha256") != campaign.manifest_sha256:
        raise ValueError("transition-cost summary manifest does not match the campaign")
    if resolved_summary.get("machine_profile_sha256") != campaign.machine_profile_sha256:
        raise ValueError("transition-cost summary machine profile does not match the campaign")
    if resolved_summary.get("successful_experiments") != campaign.planned_experiments:
        raise ValueError("transition-cost summary does not cover the full frozen campaign")

    core = {
        "schema": SCHEMA,
        "study_id": campaign.study_id,
        "manifest_sha256": campaign.manifest_sha256,
        "campaign_sha256": campaign.campaign_sha256,
        "summary_sha256": _canonical_sha256(resolved_summary),
        "machine_profile_sha256": campaign.machine_profile_sha256,
        "machine_fingerprint_sha256": campaign.machine_fingerprint_sha256,
        "source_candidate_id": campaign.source_candidate_id,
        "target_candidate_id": campaign.target_candidate_id,
        "source_manifest_sha256": campaign.source_manifest_sha256,
        "target_manifest_sha256": campaign.target_manifest_sha256,
        "experiment_count": campaign.planned_experiments,
        "repetitions_per_experiment": (
            campaign.entries[0].report.config.repetitions if campaign.entries else 0
        ),
        "total_timing_observations": sum(len(entry.report.rows) for entry in campaign.entries),
        "total_reader_observations": sum(
            row.reads for entry in campaign.entries for row in entry.report.rows
        ),
        "invalid_reader_observations": 0,
        "primary_metric": "migrate_validate_activate_ns_per",
        "secondary_metrics": ["rollback_ns_per", "round_trip_transition_ns_per"],
        "evidence_state": EVIDENCE_STATE,
        "claim_scope": "MEASURED_TRANSITION_COST_FOR_FROZEN_RQ7_MATRIX_ON_ONE_MACHINE",
        "truth_boundaries": [
            "This attestation establishes execution and measured transition-cost observations for the complete frozen RQ7 matrix on one machine/toolchain identity.",
            "It does not establish that migration cost scales according to a particular model; inferential analysis is separate.",
            "It does not establish performance superiority, cross-machine generalization, concurrent-writer migration, cross-process hot replacement, or production SLA behavior.",
            "GitHub Actions smoke measurements are categorically ineligible for this attestation.",
        ],
    }
    return {**core, "attestation_sha256": _canonical_sha256(core)}


def canonical_transition_cost_evidence_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def validate_generated_migration_transition_cost_evidence_bytes(data: bytes) -> EvidenceValidation:
    errors: list[str] = []
    try:
        payload = json.loads(data.decode("utf-8"))
    except UnicodeDecodeError:
        return EvidenceValidation(ROLE, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("attestation is not UTF-8",))
    except json.JSONDecodeError as exc:
        return EvidenceValidation(ROLE, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", (f"invalid JSON: {exc.msg}",))
    if not isinstance(payload, dict):
        return EvidenceValidation(ROLE, False, "EVIDENCE_STRUCTURAL_VALIDATION_FAILED", ("top-level JSON value must be an object",))

    if payload.get("schema") != SCHEMA:
        errors.append("unexpected transition-cost evidence schema")
    if payload.get("study_id") != "rq7-generated-migration-v1":
        errors.append("transition-cost evidence must be RQ7 v1")
    if payload.get("evidence_state") != EVIDENCE_STATE:
        errors.append("unexpected transition-cost evidence_state")
    if payload.get("claim_scope") != "MEASURED_TRANSITION_COST_FOR_FROZEN_RQ7_MATRIX_ON_ONE_MACHINE":
        errors.append("unexpected transition-cost claim_scope")
    for field in (
        "manifest_sha256",
        "campaign_sha256",
        "summary_sha256",
        "machine_profile_sha256",
        "machine_fingerprint_sha256",
        "source_manifest_sha256",
        "target_manifest_sha256",
        "attestation_sha256",
    ):
        if not _valid_sha256(payload.get(field)):
            errors.append(f"invalid {field}")
    source = str(payload.get("source_candidate_id", ""))
    target = str(payload.get("target_candidate_id", ""))
    if not source or not target or source == target:
        errors.append("source/target candidate identities must be distinct and non-empty")
    for field in ("experiment_count", "repetitions_per_experiment", "total_timing_observations", "total_reader_observations"):
        value = payload.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            errors.append(f"{field} must be a positive integer")
    if payload.get("invalid_reader_observations") != 0:
        errors.append("invalid_reader_observations must equal zero")
    if payload.get("primary_metric") != "migrate_validate_activate_ns_per":
        errors.append("unexpected primary_metric")
    if payload.get("secondary_metrics") != ["rollback_ns_per", "round_trip_transition_ns_per"]:
        errors.append("unexpected secondary_metrics")
    experiment_count = payload.get("experiment_count")
    repetitions = payload.get("repetitions_per_experiment")
    observations = payload.get("total_timing_observations")
    if isinstance(experiment_count, int) and isinstance(repetitions, int) and isinstance(observations, int):
        if observations != experiment_count * repetitions:
            errors.append("total_timing_observations must equal experiment_count * repetitions_per_experiment")

    if _valid_sha256(payload.get("attestation_sha256")):
        core = {key: value for key, value in payload.items() if key != "attestation_sha256"}
        if _canonical_sha256(core) != payload.get("attestation_sha256"):
            errors.append("attestation_sha256 does not match attestation content")

    return EvidenceValidation(
        ROLE,
        not errors,
        "EVIDENCE_STRUCTURAL_VALIDATION_PASSED" if not errors else "EVIDENCE_STRUCTURAL_VALIDATION_FAILED",
        (
            "validated complete-local RQ7 transition-cost attestation identities, observation counts and zero-invalid-reader invariant",
        )
        if not errors
        else tuple(errors),
    )
