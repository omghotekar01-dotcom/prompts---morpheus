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

from app.access_trace_validation import evaluate_synthetic_classifier  # noqa: E402


def _csv_ints(raw: str) -> tuple[int, ...]:
    try:
        values = tuple(int(token.strip()) for token in raw.split(",") if token.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected comma-separated integers") from exc
    if not values:
        raise argparse.ArgumentTypeError("at least one integer is required")
    return values


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate MORPHEUS access-trace classification heuristics against deterministic synthetic generators."
    )
    parser.add_argument("--seeds", type=_csv_ints, default=(17, 1337, 2027))
    parser.add_argument("--sample-counts", type=_csv_ints, default=(1000, 5000))
    parser.add_argument("--domain-sizes", type=_csv_ints, default=(100, 1000))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        report = evaluate_synthetic_classifier(
            seeds=args.seeds,
            sample_counts=args.sample_counts,
            domain_sizes=args.domain_sizes,
        ).as_dict()
    except ValueError as exc:
        print(f"morpheus access trace classifier evaluation: {exc}", file=sys.stderr)
        return 2

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "case_count": report["case_count"],
        "overall_accuracy": report["overall_accuracy"],
        "eligible_for_runtime_automatic_promotion": report["eligible_for_runtime_automatic_promotion"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
