from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.research import PredictionPoint, evaluate_predictions  # noqa: E402


def _git_commit() -> str | None:
    try:
        process = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = process.stdout.strip()
    return value if process.returncode == 0 and value else None


def _load(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("input JSON must be an object")
    return payload, digest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate MORPHEUS predicted costs against caller-supplied held-out measurements."
    )
    parser.add_argument("input", type=Path, help="JSON file containing metric and prediction points")
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    args = parser.parse_args()

    payload, input_sha256 = _load(args.input)
    raw_points = payload.get("points")
    if not isinstance(raw_points, list):
        raise ValueError("input JSON must contain a points array")

    points = [
        PredictionPoint(
            label=str(item["label"]),
            predicted=float(item["predicted"]),
            measured=float(item["measured"]),
        )
        for item in raw_points
    ]
    evaluation = evaluate_predictions(points)

    report = {
        "schema_version": 1,
        "protocol": "morpheus-heldout-prediction-evaluation-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "source_commit": _git_commit(),
        "input_file": args.input.name,
        "input_sha256": input_sha256,
        "metric": str(payload.get("metric", "unspecified_cost")),
        "lower_is_better": True,
        "evaluation": evaluation.as_dict(),
        "truth_note": (
            "MORPHEUS evaluated caller-supplied measurements. This report does not independently prove "
            "how those measurements were collected; preserve the benchmark manifest alongside it."
        ),
    }
    rendered = json.dumps(report, sort_keys=True, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
