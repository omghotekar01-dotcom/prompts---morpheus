#!/usr/bin/env python3
"""Run MORPHEUS ordered-index erase measurements reproducibly."""
from __future__ import annotations

import argparse
import csv
import math
import subprocess
import tempfile
from pathlib import Path

FIELDS = {"implementation", "size", "erase_count", "repetitions", "seed", "ns_per_erase", "final_size", "checksum"}
IMPLEMENTATIONS = {"ordered_tree_rebuild", "bplus_tree_rebalanced", "std_map"}
DEFAULT_SIZES = "256,512,1024,2048,4096,8192"
DEFAULT_SEEDS = "1337,7331,424242"


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


def run_one(executable: Path, size: int, erase_count: int, repetitions: int, seed: int) -> list[dict[str, str]]:
    command = [
        str(executable), "--csv", "--size", str(size), "--erase-count", str(erase_count),
        "--repetitions", str(repetitions), "--seed", str(seed),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    reader = csv.DictReader(result.stdout.splitlines())
    if set(reader.fieldnames or ()) != FIELDS:
        raise RuntimeError(f"unexpected CSV fields: {reader.fieldnames!r}")
    rows = list(reader)
    if len(rows) != len(IMPLEMENTATIONS):
        raise RuntimeError(f"expected {len(IMPLEMENTATIONS)} benchmark rows, got {len(rows)}")

    seen: set[str] = set()
    final_sizes: dict[str, int] = {}
    checksums: dict[str, int] = {}
    for row in rows:
        implementation = row["implementation"]
        if implementation not in IMPLEMENTATIONS or implementation in seen:
            raise RuntimeError(f"unexpected/duplicate implementation row: {implementation!r}")
        seen.add(implementation)
        try:
            observed_size = int(row["size"])
            observed_erase_count = int(row["erase_count"])
            observed_repetitions = int(row["repetitions"])
            observed_seed = int(row["seed"])
            ns_per_erase = float(row["ns_per_erase"])
            final_size = int(row["final_size"])
            checksum = int(row["checksum"])
        except ValueError as exc:
            raise RuntimeError(f"invalid numeric benchmark row: {row}") from exc
        if (observed_size, observed_erase_count, observed_repetitions, observed_seed) != (size, erase_count, repetitions, seed):
            raise RuntimeError(f"benchmark metadata mismatch: {row}")
        if not math.isfinite(ns_per_erase) or ns_per_erase < 0:
            raise RuntimeError(f"invalid timing: {row}")
        expected_final = size - erase_count
        if final_size != expected_final:
            raise RuntimeError(f"unexpected final size: {row}")
        final_sizes[implementation] = final_size
        checksums[implementation] = checksum

    if seen != IMPLEMENTATIONS or len(set(final_sizes.values())) != 1 or len(set(checksums.values())) != 1:
        raise RuntimeError("benchmark implementation result topology mismatch")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Sweep MORPHEUS ordered-index erase benchmark")
    parser.add_argument("executable", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sizes", default=DEFAULT_SIZES)
    parser.add_argument("--seeds", default=DEFAULT_SEEDS)
    parser.add_argument("--erase-count", type=int, default=32)
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args()

    if not args.executable.is_file():
        parser.error(f"benchmark executable not found: {args.executable}")
    if args.erase_count < 1:
        parser.error("--erase-count must be positive")
    if args.repetitions < 1:
        parser.error("--repetitions must be positive")
    sizes = parse_csv_ints(args.sizes, "--sizes")
    seeds = parse_csv_ints(args.seeds, "--seeds")
    if any(size <= args.erase_count or size > 0xFFFFFFFF for size in sizes):
        parser.error("every size must be greater than erase-count and fit uint32")
    if any(seed < 0 or seed > 0xFFFFFFFF for seed in seeds):
        parser.error("all seeds must fit uint32")

    rows: list[dict[str, str]] = []
    for size in sizes:
        for seed in seeds:
            rows.extend(run_one(args.executable, size, args.erase_count, args.repetitions, seed))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["implementation", "size", "erase_count", "repetitions", "seed", "ns_per_erase", "final_size", "checksum"]
    with tempfile.NamedTemporaryFile("w", newline="", encoding="utf-8", dir=args.output.parent, delete=False) as stream:
        temp_path = Path(stream.name)
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    temp_path.replace(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
