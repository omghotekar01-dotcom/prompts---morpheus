#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.generated_migration_campaign import (  # noqa: E402
    freeze_generated_migration_campaign,
    run_generated_migration_campaign,
    summarize_generated_migration_campaign,
)
from app.generated_migration_transition_evidence import (  # noqa: E402
    build_generated_migration_transition_cost_evidence,
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
    parser.add_argument("--limit", type=int, default=None, help="Execute only the first N frozen experiments for an explicit partial run")
    parser.add_argument("--compile-timeout", type=int, default=120, help="Per-experiment compiler timeout in seconds")
    parser.add_argument("--run-timeout", type=int, default=120, help="Per-experiment benchmark timeout in seconds")
    return parser


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = _parser().parse_args()
    try:
        spec = parse_workload_text(args.spec.read_text(encoding="utf-8"))
        matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
        if not isinstance(matrix, dict):
            raise ValueError("matrix must be a JSON object")
        frozen_manifest = freeze_generated_migration_campaign(matrix)
        campaign = run_generated_migration_campaign(
            spec,
            matrix,
            limit=args.limit,
            compile_timeout_seconds=args.compile_timeout,
            run_timeout_seconds=args.run_timeout,
        )
        summary = summarize_generated_migration_campaign(campaign)
        if campaign.manifest_sha256 != frozen_manifest.manifest_sha256:
            raise ValueError("campaign manifest identity differs from independently frozen RQ7 matrix")

        output_dir = args.output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = output_dir / "generated-migration-experiment-manifest.json"
        machine_path = output_dir / "generated-migration-machine-profile.json"
        campaign_path = output_dir / "generated-migration-campaign.json"
        summary_path = output_dir / "generated-migration-summary.json"
        attestation_path = output_dir / "generated-migration-transition-cost-evidence.json"

        _write_json(manifest_path, frozen_manifest.as_dict())
        _write_json(machine_path, campaign.machine_profile)
        _write_json(campaign_path, campaign.as_dict())
        _write_json(summary_path, summary)

        attestation_created = False
        if (
            campaign.complete
            and campaign.comparable_environment
            and campaign.evidence_state == "GENERATED_MIGRATION_CAMPAIGN_COMPLETE_LOCAL_MEASUREMENTS"
        ):
            attestation = build_generated_migration_transition_cost_evidence(campaign, summary=summary)
            _write_json(attestation_path, attestation)
            attestation_created = True
        elif attestation_path.exists():
            # Prevent stale complete-local evidence from surviving a later partial/CI run into the same directory.
            attestation_path.unlink()

        result = {
            "schema": "morpheus-generated-migration-campaign-run-v2",
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
            "experiment_manifest_path": str(manifest_path),
            "machine_profile_path": str(machine_path),
            "campaign_path": str(campaign_path),
            "summary_path": str(summary_path),
            "transition_cost_attestation_created": attestation_created,
            "transition_cost_attestation_path": str(attestation_path) if attestation_created else None,
            "truth_boundary": (
                "Successful execution creates provenance-bound generated-migration measurement evidence. "
                "The transition-cost attestation is emitted only for a complete non-CI local RQ7 campaign; "
                "GitHub Actions measurements remain smoke evidence regardless of completion."
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
