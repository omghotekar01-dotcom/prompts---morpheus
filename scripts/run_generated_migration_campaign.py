#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.generated_migration_campaign import (  # noqa: E402
    GeneratedMigrationCampaignReport,
    freeze_generated_migration_campaign,
    run_generated_migration_campaign,
    summarize_generated_migration_campaign,
)
from app.generated_migration_transition_evidence import build_generated_migration_transition_cost_evidence  # noqa: E402
from app.measurement_environment import (  # noqa: E402
    build_measurement_environment_record,
    capture_measurement_environment_snapshot,
)
from app.parser import SpecParseError, parse_workload_text  # noqa: E402


DEFAULT_MATRIX = REPO_ROOT / "research" / "matrices" / "rq7-generated-migration.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Execute the frozen MORPHEUS RQ7 generated-candidate migration transition-cost campaign. "
            "CI results remain smoke evidence; use a controlled local machine for research measurements."
        )
    )
    parser.add_argument("spec", type=Path, help="MORPHEUS workload specification (YAML or JSON)")
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX, help="Frozen RQ7 experiment matrix JSON")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for provenance-bound RQ7 JSON evidence")
    parser.add_argument("--resume-from", type=Path, default=None, help="Prior partial/full campaign JSON or checkpoint to verify and reuse")
    parser.add_argument("--checkpoint", type=Path, default=None, help="Checkpoint JSON path; defaults inside --output-dir")
    parser.add_argument("--limit", type=int, default=None, help="Execute only the first N frozen experiments for an explicit partial run")
    parser.add_argument("--compile-timeout", type=int, default=120, help="Generated benchmark compiler timeout in seconds")
    parser.add_argument("--run-timeout", type=int, default=120, help="Per-cell benchmark timeout in seconds")
    parser.add_argument("--operator-note", default=None, help="Optional operator note stored only in measurement-environment provenance")
    return parser


def _write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    try:
        temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _load_json_object(path: Path, *, label: str) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _resume_entry_ids(payload: dict[str, object] | None) -> set[str]:
    if payload is None:
        return set()
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return set()
    return {
        str(entry.get("experiment_id"))
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("experiment_id", "")).strip()
    }


def main() -> int:
    args = _parser().parse_args()
    try:
        spec = parse_workload_text(args.spec.read_text(encoding="utf-8"))
        matrix = _load_json_object(args.matrix, label="matrix")
        frozen_manifest = freeze_generated_migration_campaign(matrix)

        output_dir = args.output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = args.checkpoint.resolve() if args.checkpoint is not None else output_dir / "generated-migration-checkpoint.json"
        resume_checkpoint = _load_json_object(args.resume_from, label="resume checkpoint") if args.resume_from is not None else None
        resume_ids = _resume_entry_ids(resume_checkpoint)

        def persist_checkpoint(partial: GeneratedMigrationCampaignReport) -> None:
            _write_json_atomic(checkpoint_path, partial.as_dict())

        environment_start = capture_measurement_environment_snapshot()
        campaign = run_generated_migration_campaign(
            spec,
            matrix,
            resume_checkpoint=resume_checkpoint,
            checkpoint_callback=persist_checkpoint,
            limit=args.limit,
            compile_timeout_seconds=args.compile_timeout,
            run_timeout_seconds=args.run_timeout,
        )
        environment_end = capture_measurement_environment_snapshot()
        summary = summarize_generated_migration_campaign(campaign)
        if campaign.manifest_sha256 != frozen_manifest.manifest_sha256:
            raise ValueError("campaign manifest identity differs from independently frozen RQ7 matrix")

        manifest_path = output_dir / "generated-migration-experiment-manifest.json"
        machine_path = output_dir / "generated-migration-machine-profile.json"
        campaign_path = output_dir / "generated-migration-campaign.json"
        summary_path = output_dir / "generated-migration-summary.json"
        attestation_path = output_dir / "generated-migration-transition-cost-evidence.json"
        environment_path = output_dir / "generated-migration-measurement-environment.json"

        _write_json_atomic(manifest_path, frozen_manifest.as_dict())
        _write_json_atomic(machine_path, campaign.machine_profile)
        _write_json_atomic(campaign_path, campaign.as_dict())
        _write_json_atomic(summary_path, summary)

        newly_measured_ids = [entry.experiment_id for entry in campaign.entries if entry.experiment_id not in resume_ids]
        environment_record_created = False
        environment_record_complete_coverage = False
        if newly_measured_ids:
            resumed_from_sha = (
                str(resume_checkpoint.get("campaign_sha256"))
                if resume_checkpoint is not None and isinstance(resume_checkpoint.get("campaign_sha256"), str)
                else None
            )
            environment_record = build_measurement_environment_record(
                environment_start,
                environment_end,
                campaign_sha256=campaign.campaign_sha256,
                machine_fingerprint_sha256=campaign.machine_fingerprint_sha256,
                covered_experiment_ids=newly_measured_ids,
                planned_experiments=campaign.planned_experiments,
                resumed_from_campaign_sha256=resumed_from_sha,
                operator_note=args.operator_note,
            )
            _write_json_atomic(environment_path, environment_record)
            environment_record_created = True
            environment_record_complete_coverage = bool(
                environment_record["coverage"]["complete_single_invocation_coverage"]
            )
        elif environment_path.exists():
            environment_path.unlink()

        attestation_created = False
        if campaign.complete and campaign.comparable_environment and campaign.evidence_state == "GENERATED_MIGRATION_CAMPAIGN_COMPLETE_LOCAL_MEASUREMENTS":
            attestation = build_generated_migration_transition_cost_evidence(campaign, summary=summary)
            _write_json_atomic(attestation_path, attestation)
            attestation_created = True
        elif attestation_path.exists():
            attestation_path.unlink()

        checkpoint_retained = not campaign.complete
        if campaign.complete and checkpoint_path.exists():
            checkpoint_path.unlink()

        result = {
            "schema": "morpheus-generated-migration-campaign-run-v4",
            "study_id": campaign.study_id,
            "campaign_sha256": campaign.campaign_sha256,
            "manifest_sha256": campaign.manifest_sha256,
            "machine_profile_sha256": campaign.machine_profile_sha256,
            "machine_fingerprint_sha256": campaign.machine_fingerprint_sha256,
            "planned_experiments": campaign.planned_experiments,
            "executed_experiments": campaign.executed_experiments,
            "complete": campaign.complete,
            "comparable_environment": campaign.comparable_environment,
            "evidence_state": campaign.evidence_state,
            "resumed_from": str(args.resume_from.resolve()) if args.resume_from is not None else None,
            "newly_measured_experiments": len(newly_measured_ids),
            "checkpoint_path": str(checkpoint_path),
            "checkpoint_retained": checkpoint_retained,
            "experiment_manifest_path": str(manifest_path),
            "machine_profile_path": str(machine_path),
            "campaign_path": str(campaign_path),
            "summary_path": str(summary_path),
            "measurement_environment_record_created": environment_record_created,
            "measurement_environment_complete_single_invocation_coverage": environment_record_complete_coverage,
            "measurement_environment_path": str(environment_path) if environment_record_created else None,
            "transition_cost_attestation_created": attestation_created,
            "transition_cost_attestation_path": str(attestation_path) if attestation_created else None,
            "truth_boundary": (
                "Each accepted RQ7 cell is atomically checkpointed as a content-hashed partial campaign. Resume reuses only "
                "verified cells and measurement-environment coverage names only cells newly measured in this invocation. A single "
                "environment record can claim complete campaign coverage only for a fresh 24-cell invocation. Environment metadata "
                "is observation, not laboratory-control proof. The transition-cost attestation remains unavailable to CI-smoke, "
                "partial or mixed-environment campaigns."
            ),
        }
        print(json.dumps(result, sort_keys=True))

        executed_successfully = bool(campaign.entries) and all(entry.report.success for entry in campaign.entries)
        if args.limit is not None:
            return 0 if executed_successfully else 3
        return 0 if campaign.complete else 3
    except (OSError, TypeError, ValueError, json.JSONDecodeError, SpecParseError) as exc:
        print(f"generated migration campaign failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
