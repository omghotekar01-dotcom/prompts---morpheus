#!/usr/bin/env python3
"""Run reproducible MORPHEUS adaptive-bitmap cardinality sweeps.

The benchmark executable owns timing; this script orchestrates repeated
cardinality/seed runs, validates its machine-readable contract, and emits one
normalized CSV stream suitable for later analysis. It deliberately does not
claim threshold optimality by itself.
"""

from __future__ import annotations

import argparse
import csv
import io
import subprocess
import sys
from pathlib import Path

DEFAULT_CARDINALITIES = (256, 512, 1024, 2048, 3072, 4095, 4096, 4097, 6144, 8192, 16384, 32768, 49152, 65536)
FIELDNAMES = ["operation", "cardinality", "repetitions", "seed", "dense_containers", "ns_per_op", "result_size"]
EXPECTED_OPERATIONS = {"intersection", "union", "contains", "materialize"}


def parse_cardinalities(value: str) -> list[int]:
    try:
        values = sorted({int(item.strip()) for item in value.split(",") if item.strip()})
    except ValueError as error:
        raise argparse.ArgumentTypeError("cardinalities must be integers in [1, 65536]") from error
    if not values or any(item < 1 or item > 65536 for item in values):
        raise argparse.ArgumentTypeError("cardinalities must be integers in [1, 65536]")
    return values


def read_rows(output: str, cardinality: int, repetitions: int, seed: int) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(output))
    if reader.fieldnames != FIELDNAMES:
        raise RuntimeError(f"unexpected benchmark CSV header: {reader.fieldnames!r}")
    rows = list(reader)
    operations = {row["operation"] for row in rows}
    if len(rows) != len(EXPECTED_OPERATIONS) or operations != EXPECTED_OPERATIONS:
        raise RuntimeError(f"benchmark emitted unexpected operations: {sorted(operations)!r}")
    for row in rows:
        if int(row["cardinality"]) != cardinality or int(row["repetitions"]) != repetitions or int(row["seed"]) != seed:
            raise RuntimeError("benchmark CSV metadata does not match requested sweep point")
        if float(row["ns_per_op"]) < 0 or int(row["result_size"]) < 0 or int(row["dense_containers"]) < 0:
            raise RuntimeError("benchmark CSV contains invalid negative measurements")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Sweep MORPHEUS adaptive bitmap benchmark cardinalities")
    parser.add_argument("benchmark", type=Path, help="path to morpheus_compressed_bitmap_bench executable")
    parser.add_argument("--cardinalities", type=parse_cardinalities,
                        default=list(DEFAULT_CARDINALITIES), help="comma-separated cardinalities")
    parser.add_argument("--repetitions", type=int, default=500)
    parser.add_argument("--seeds", type=int, default=5, help="number of deterministic seeds")
    parser.add_argument("--seed-base", type=int, default=1337)
    parser.add_argument("--output", type=Path, help="write CSV here instead of stdout")
    args = parser.parse_args()

    if args.repetitions < 1 or args.seeds < 1:
        parser.error("--repetitions and --seeds must be positive")
    if args.seed_base < 0 or args.seed_base + args.seeds - 1 > 0xFFFFFFFF:
        parser.error("seed range must fit uint32")
    if not args.benchmark.is_file():
        parser.error(f"benchmark executable not found: {args.benchmark}")

    rows: list[dict[str, str]] = []
    for cardinality in args.cardinalities:
        for seed_offset in range(args.seeds):
            seed = args.seed_base + seed_offset
            command = [str(args.benchmark), "--cardinality", str(cardinality),
                       "--repetitions", str(args.repetitions), "--seed", str(seed), "--csv"]
            completed = subprocess.run(command, check=True, capture_output=True, text=True)
            rows.extend(read_rows(completed.stdout, cardinality, args.repetitions, seed))

    stream = args.output.open("w", newline="", encoding="utf-8") if args.output else sys.stdout
    try:
        writer = csv.DictWriter(stream, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if args.output:
            stream.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
