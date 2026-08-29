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

from app.generated_migration_campaign_io import load_generated_migration_campaign  # noqa: E402
from app.rq7_confirmatory_analysis import analyze_rq7_confirmatory  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the versioned MORPHEUS H7 confirmatory analysis over a persisted complete-local RQ7 campaign. "
            "This command performs no native benchmark execution."
        )
    )
    parser.add_argument("campaign", type=Path, help="generated-migration-campaign.json from the RQ7 runner")
    parser.add_argument("--output", type=Path, required=True, help="Output JSON for morpheus-rq7-confirmatory-analysis-v1")
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


def main() -> int:
    args = _parser().parse_args()
    try:
        payload = json.loads(args.campaign.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("campaign must be a JSON object")
        campaign = load_generated_migration_campaign(payload)
        analysis = analyze_rq7_confirmatory(campaign)
        _write_json_atomic(args.output.resolve(), analysis)
        print(
            json.dumps(
                {
                    "schema": "morpheus-rq7-confirmatory-analysis-run-v1",
                    "study_id": analysis["study_id"],
                    "campaign_sha256": analysis["campaign_sha256"],
                    "analysis_sha256": analysis["analysis_sha256"],
                    "h7_decision": analysis["h7_decision"],
                    "output": str(args.output.resolve()),
                    "truth_boundary": (
                        "This is offline analysis of the supplied persisted campaign. It neither reruns measurements nor broadens "
                        "the campaign's single-workload, single-candidate-pair, single-machine evidence scope."
                    ),
                },
                sort_keys=True,
            )
        )
        return 0
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"rq7 confirmatory analysis failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
