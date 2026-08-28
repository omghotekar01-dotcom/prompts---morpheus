#!/usr/bin/env python3
"""Summarize MORPHEUS adaptive-bitmap sweep CSV without overstating conclusions.

Consumes normalized output from sweep_bitmap_benchmark.py, validates that the
measurement topology is complete and numerically sane, aggregates repeated
seeds, and reports medians plus spread. The report is evidence for threshold
review; it does not automatically rewrite production thresholds.
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path

REQUIRED = {"operation", "cardinality", "repetitions", "seed", "dense_containers", "ns_per_op", "result_size"}
EXPECTED_OPERATIONS = {"intersection", "union", "contains", "materialize"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze MORPHEUS bitmap sweep CSV")
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("--output", type=Path, help="optional summary CSV")
    parser.add_argument("--expect-samples", type=int, help="require exactly this many samples for every cardinality/operation pair")
    args = parser.parse_args()

    if args.expect_samples is not None and args.expect_samples < 1:
        parser.error("--expect-samples must be >= 1")
    if not args.csv_file.is_file():
        parser.error(f"CSV not found: {args.csv_file}")

    grouped: dict[tuple[int, str], list[float]] = defaultdict(list)
    dense: dict[tuple[int, str], list[int]] = defaultdict(list)
    seeds: dict[tuple[int, str], set[int]] = defaultdict(set)
    repetitions_by_key: dict[tuple[int, str], set[int]] = defaultdict(set)
    cardinalities: set[int] = set()
    with args.csv_file.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if set(reader.fieldnames or ()) != REQUIRED:
            parser.error(f"unexpected CSV fields: {reader.fieldnames!r}")
        for row_number, row in enumerate(reader, start=2):
            try:
                cardinality = int(row["cardinality"])
                operation = row["operation"]
                ns = float(row["ns_per_op"])
                dense_containers = int(row["dense_containers"])
                result_size = int(row["result_size"])
                repetitions = int(row["repetitions"])
                seed = int(row["seed"])
            except (TypeError, ValueError) as exc:
                parser.error(f"invalid numeric field on CSV row {row_number}: {exc}")

            if cardinality < 1:
                parser.error(f"cardinality must be >= 1 on CSV row {row_number}")
            if operation not in EXPECTED_OPERATIONS:
                parser.error(f"unexpected operation {operation!r} on CSV row {row_number}")
            if not math.isfinite(ns) or ns < 0:
                parser.error(f"ns_per_op must be finite and non-negative on CSV row {row_number}")
            if dense_containers < 0 or result_size < 0 or repetitions < 1 or seed < 0:
                parser.error(f"invalid measurement metadata on CSV row {row_number}")

            key = (cardinality, operation)
            if seed in seeds[key]:
                parser.error(f"duplicate seed {seed} for cardinality {cardinality}, operation {operation}")
            cardinalities.add(cardinality)
            grouped[key].append(ns)
            dense[key].append(dense_containers)
            seeds[key].add(seed)
            repetitions_by_key[key].add(repetitions)

    if not grouped:
        parser.error("CSV contains no measurements")

    for cardinality in sorted(cardinalities):
        present = {operation for candidate, operation in grouped if candidate == cardinality}
        if present != EXPECTED_OPERATIONS:
            missing = sorted(EXPECTED_OPERATIONS - present)
            extra = sorted(present - EXPECTED_OPERATIONS)
            parser.error(f"incomplete operation topology for cardinality {cardinality}: missing={missing}, extra={extra}")

        sample_counts = {operation: len(grouped[(cardinality, operation)]) for operation in EXPECTED_OPERATIONS}
        if len(set(sample_counts.values())) != 1:
            parser.error(f"inconsistent sample counts for cardinality {cardinality}: {sample_counts}")
        if args.expect_samples is not None and next(iter(sample_counts.values())) != args.expect_samples:
            parser.error(f"expected {args.expect_samples} samples for cardinality {cardinality}, got {sample_counts}")

        expected_seeds = seeds[(cardinality, next(iter(EXPECTED_OPERATIONS)))]
        for operation in EXPECTED_OPERATIONS:
            key = (cardinality, operation)
            if seeds[key] != expected_seeds:
                parser.error(f"seed topology differs across operations for cardinality {cardinality}")
            if len(repetitions_by_key[key]) != 1:
                parser.error(f"inconsistent repetitions for cardinality {cardinality}, operation {operation}")

    fields = ["cardinality", "operation", "samples", "median_ns_per_op", "min_ns_per_op", "max_ns_per_op", "median_dense_containers"]
    output_rows = []
    for key in sorted(grouped):
        values = grouped[key]
        output_rows.append({
            "cardinality": key[0], "operation": key[1], "samples": len(values),
            "median_ns_per_op": f"{statistics.median(values):.3f}",
            "min_ns_per_op": f"{min(values):.3f}", "max_ns_per_op": f"{max(values):.3f}",
            "median_dense_containers": f"{statistics.median(dense[key]):.1f}",
        })

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        stream = args.output.open("w", newline="", encoding="utf-8")
    else:
        import sys
        stream = sys.stdout
    try:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)
    finally:
        if args.output:
            stream.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
