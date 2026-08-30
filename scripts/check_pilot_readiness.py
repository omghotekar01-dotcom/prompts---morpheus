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

from app.pilot_readiness import build_pilot_readiness  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate MORPHEUS startup readiness for the declared guarded single-node pilot scope. "
            "Exit 0 means all required local preflight checks passed; exit 3 means the pilot must remain blocked."
        )
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Emit one-line JSON rather than indented JSON.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        report = build_pilot_readiness()
    except Exception as exc:
        print(
            json.dumps(
                {
                    "schema": "morpheus-pilot-readiness-cli-error-v1",
                    "state": "PILOT_PREFLIGHT_INTERNAL_FAILURE",
                    "error_type": type(exc).__name__,
                    "truth_boundary": "The preflight failed closed and does not expose exception text that may contain local paths or configuration detail.",
                },
                sort_keys=True,
            )
        )
        return 2

    if args.compact:
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    else:
        print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report.get("ready") is True else 3


if __name__ == "__main__":
    raise SystemExit(main())
