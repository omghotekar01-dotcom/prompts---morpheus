from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.parser import parse_workload_text, semantic_hash  # noqa: E402
from app.search_quality import compare_beam_to_exhaustive  # noqa: E402


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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare MORPHEUS beam-search decisions with a bounded exhaustive model oracle."
    )
    parser.add_argument("workload", type=Path, help="MWS YAML/JSON workload")
    parser.add_argument("--beam-width", type=int, default=128)
    parser.add_argument("--exhaustive-limit", type=int, default=100000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    raw = args.workload.read_text(encoding="utf-8")
    raw_sha256 = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    spec = parse_workload_text(raw)
    report = compare_beam_to_exhaustive(
        spec,
        beam_width=args.beam_width,
        exhaustive_limit=args.exhaustive_limit,
    )

    payload = {
        "schema_version": 1,
        "protocol": "morpheus-search-quality-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "source_commit": _git_commit(),
        "workload_file": args.workload.name,
        "workload_source_sha256": raw_sha256,
        "workload_semantic_hash": semantic_hash(spec),
        "beam_width": args.beam_width,
        "exhaustive_limit": args.exhaustive_limit,
        "report": report.as_dict(),
        "truth_note": (
            "This compares beam search with MORPHEUS's exhaustive modeled objective on a bounded space. "
            "It measures search heuristic fidelity, not real-hardware prediction accuracy."
        ),
    }
    rendered = json.dumps(payload, sort_keys=True, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
