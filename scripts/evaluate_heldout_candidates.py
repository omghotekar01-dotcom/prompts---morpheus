#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.heldout_evaluation import HeldoutCandidateMeasurement, evaluate_heldout_candidate_groups


REQUIRED_COLUMNS = {"workload_id", "candidate_id", "predicted", "measured"}


def load_csv(path: Path) -> list[HeldoutCandidateMeasurement]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("held-out CSV is missing a header")
        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise ValueError(f"held-out CSV missing required columns: {sorted(missing)}")
        items: list[HeldoutCandidateMeasurement] = []
        for row_number, row in enumerate(reader, start=2):
            try:
                items.append(
                    HeldoutCandidateMeasurement(
                        workload_id=str(row["workload_id"]).strip(),
                        candidate_id=str(row["candidate_id"]).strip(),
                        predicted=float(row["predicted"]),
                        measured=float(row["measured"]),
                    )
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid numeric value at CSV row {row_number}") from exc
    return items


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate MORPHEUS predicted candidate costs against caller-supplied held-out measurements."
    )
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--bootstrap-rounds", type=int, default=2000)
    parser.add_argument("--bootstrap-seed", type=int, default=1337)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        raw = args.input_csv.read_bytes()
        measurements = load_csv(args.input_csv)
        report = evaluate_heldout_candidate_groups(
            measurements,
            top_k=args.top_k,
            bootstrap_rounds=args.bootstrap_rounds,
            bootstrap_seed=args.bootstrap_seed,
        )
    except (OSError, ValueError) as exc:
        print(f"morpheus held-out evaluation: {exc}", file=sys.stderr)
        return 2

    payload = {
        "schema": "morpheus-heldout-cost-model-evaluation-v1",
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "input_file": args.input_csv.name,
        "report": report.as_dict(),
        "evidence_state": report.evidence_state,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "evidence_state": report.evidence_state}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
