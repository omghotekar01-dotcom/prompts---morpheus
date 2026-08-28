#!/usr/bin/env python3
"""Run the MORPHEUS sparse-vs-dense container crossover benchmark reproducibly."""
from __future__ import annotations

import argparse
import csv
import math
import subprocess
import tempfile
from pathlib import Path

FIELDS = {"representation", "operation", "cardinality", "repetitions", "seed", "ns_per_op", "result_size"}
OPERATIONS = {"intersection", "union", "contains", "materialize"}
REPRESENTATIONS = {"sparse", "dense"}
DEFAULT_CARDINALITIES = "512,1024,1536,2048,2560,3072,3584,4095,4096,4097,4608,5120,6144,8192,12288,16384"


def parse_csv_ints(value: str, option: str) -> list[int]:
    try:
        parsed = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{option} requires comma-separated integers") from exc
    if not parsed:
        raise argparse.ArgumentTypeError(f"{option} cannot be empty")
    if len(parsed) != len(set(parsed)):
        raise argparse.ArgumentTypeError(f"{option} cannot contain duplicates")
    return parsed


def run_one(executable: Path, cardinality: int, repetitions: int, seed: int) -> list[dict[str, str]]:
    command = [
        str(executable),
        "--csv",
        "--cardinality", str(cardinality),
        "--repetitions", str(repetitions),
        "--seed", str(seed),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    reader = csv.DictReader(result.stdout.splitlines())
    if set(reader.fieldnames or ()) != FIELDS:
        raise RuntimeError(f"unexpected CSV fields from benchmark: {reader.fieldnames!r}")
    rows = list(reader)
    if len(rows) != len(OPERATIONS) * len(REPRESENTATIONS):
        raise RuntimeError(f"expected 8 benchmark rows, got {len(rows)}")

    seen: set[tuple[str, str]] = set()
    result_sizes: dict[str, dict[str, int]] = {operation: {} for operation in OPERATIONS}
    for row in rows:
        representation = row["representation"]
        operation = row["operation"]
        if representation not in REPRESENTATIONS or operation not in OPERATIONS:
            raise RuntimeError(f"unexpected benchmark row: representation={representation!r}, operation={operation!r}")
        key = (representation, operation)
        if key in seen:
            raise RuntimeError(f"duplicate benchmark row for {representation}/{operation}")
        seen.add(key)
        try:
            observed_cardinality = int(row["cardinality"])
            observed_repetitions = int(row["repetitions"])
            observed_seed = int(row["seed"])
            ns = float(row["ns_per_op"])
            result_size = int(row["result_size"])
        except ValueError as exc:
            raise RuntimeError(f"invalid numeric benchmark row: {row}") from exc
        if observed_cardinality != cardinality or observed_repetitions != repetitions or observed_seed != seed:
            raise RuntimeError(f"benchmark metadata mismatch: {row}")
        if not math.isfinite(ns) or ns < 0 or result_size < 0:
            raise RuntimeError(f"invalid benchmark measurement: {row}")
        result_sizes[operation][representation] = result_size

    for operation, by_representation in result_sizes.items():
        if set(by_representation) != REPRESENTATIONS:
            raise RuntimeError(f"missing representation result for {operation}")
        if by_representation["sparse"] != by_representation["dense"]:
            raise RuntimeError(f"sparse/dense result-size mismatch for {operation}: {by_representation}")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Sweep MORPHEUS sparse-vs-dense bitmap container benchmark")
    parser.add_argument("executable", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cardinalities", default=DEFAULT_CARDINALITIES)
    parser.add_argument("--seeds", default="1337,7331,424242")
    parser.add_argument("--repetitions", type=int, default=200)
    args = parser.parse_args()

    if not args.executable.is_file():
        parser.error(f"benchmark executable not found: {args.executable}")
    if args.repetitions < 1:
        parser.error("--repetitions must be positive")
    cardinalities = parse_csv_ints(args.cardinalities, "--cardinalities")
    seeds = parse_csv_ints(args.seeds, "--seeds")
    if any(cardinality < 1 or cardinality > 65536 for cardinality in cardinalities):
        parser.error("all cardinalities must be in [1, 65536]")
    if any(seed < 0 or seed > 0xFFFFFFFF for seed in seeds):
        parser.error("all seeds must fit uint32")

    rows: list[dict[str, str]] = []
    for cardinality in cardinalities:
        for seed in seeds:
            rows.extend(run_one(args.executable, cardinality, args.repetitions, seed))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["representation", "operation", "cardinality", "repetitions", "seed", "ns_per_op", "result_size"]
    with tempfile.NamedTemporaryFile("w", newline="", encoding="utf-8", dir=args.output.parent, delete=False) as stream:
        temp_path = Path(stream.name)
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    temp_path.replace(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
