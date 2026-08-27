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

from app.research_suite import PairedObservation, analyze_paired_measurements, freeze_experiment_matrix


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path | None, payload: object) -> None:
    text = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    if path is None:
        sys.stdout.write(text)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def freeze(args: argparse.Namespace) -> int:
    raw = _read_json(args.matrix)
    if not isinstance(raw, dict):
        raise ValueError("matrix input must be a JSON object")
    manifest = freeze_experiment_matrix(
        study_id=str(raw["study_id"]),
        hypothesis=str(raw["hypothesis"]),
        metric=str(raw["metric"]),
        lower_is_better=bool(raw.get("lower_is_better", True)),
        repetitions=int(raw["repetitions"]),
        seeds=[int(item) for item in raw["seeds"]],
        axes=dict(raw["axes"]),
        max_experiments=int(raw.get("max_experiments", 100_000)),
    )
    payload = manifest.as_dict()
    payload["source_matrix"] = str(args.matrix)
    payload["truth_note"] = "This file freezes planned experiments. It contains no benchmark measurements."
    _write_json(args.output, payload)
    return 0


def paired(args: argparse.Namespace) -> int:
    raw = _read_json(args.input)
    if not isinstance(raw, dict):
        raise ValueError("paired input must be a JSON object")
    observations_raw = raw.get("observations")
    if not isinstance(observations_raw, list):
        raise ValueError("paired input requires an observations array")
    observations = [
        PairedObservation(
            label=str(item["label"]),
            baseline=float(item["baseline"]),
            treatment=float(item["treatment"]),
        )
        for item in observations_raw
    ]
    report = analyze_paired_measurements(
        metric=str(raw["metric"]),
        observations=observations,
        lower_is_better=bool(raw.get("lower_is_better", True)),
        bootstrap_rounds=int(raw.get("bootstrap_rounds", 4000)),
        bootstrap_seed=int(raw.get("bootstrap_seed", 1337)),
        confidence=float(raw.get("confidence", 0.95)),
        tie_tolerance=float(raw.get("tie_tolerance", 1e-12)),
    )
    _write_json(args.output, report.as_dict())
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Freeze MORPHEUS P10 experiment matrices and analyze caller-supplied paired measurements."
    )
    sub = root.add_subparsers(dest="command", required=True)

    freeze_parser = sub.add_parser("freeze", help="Create deterministic experiment IDs from a JSON matrix.")
    freeze_parser.add_argument("matrix", type=Path)
    freeze_parser.add_argument("--output", type=Path)
    freeze_parser.set_defaults(func=freeze)

    paired_parser = sub.add_parser("paired", help="Analyze paired benchmark measurements.")
    paired_parser.add_argument("input", type=Path)
    paired_parser.add_argument("--output", type=Path)
    paired_parser.set_defaults(func=paired)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return int(args.func(args))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"morpheus research suite: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
