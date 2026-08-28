#!/usr/bin/env python3
"""Run reproducible MORPHEUS adaptive-bitmap cardinality sweeps.

The benchmark executable owns timing; this script only orchestrates repeated
cardinality/seed runs and emits one normalized CSV stream suitable for later
analysis. It deliberately does not claim threshold optimality by itself.
"""

from __future__ import annotations

import argparse
import csv
import io
import subprocess
import sys
from pathlib import Path

DEFAULT_CARDINALITIES = (256, 512, 1024, 2048, 3072, 4095, 4096, 4097, 6144, 8192, 16384, 32768, 49152, 65536)


def parse_cardinalities(value: str) -> list[int]:
    values = sorted({int(item.strip()) for item in value.split(",") if item.strip()})
    if not values or any(value < 1 or value > 65536 for value in values):
        raise argparse.ArgumentTypeError("cardinalities must be integers in [1, 65536]")
    return values


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

    rows: list[dict[str, str]] = []
    for cardinality in args.cardinalities:
        for seed_offset in range(args.seeds):
            seed = args.seed_base + seed_offset
            command = [str(args.benchmark), "--cardinality", str(cardinality),
                       "--repetitions", str(args.repetitions), "--seed", str(seed), "--csv"]
            completed = subprocess.run(command, check=True, capture_output=True, text=True)
            rows.extend(csv.DictReader(io.StringIO(completed.stdout)))

    fieldnames = ["operation", "cardinality", "repetitions", "seed", "dense_containers", "ns_per_op", "result_size"]
    stream = args.output.open("w", newline="", encoding="utf-8") if args.output else sys.stdout
    try:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if args.output:
            stream.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
