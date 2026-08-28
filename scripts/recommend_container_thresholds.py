#!/usr/bin/env python3
"""Derive conservative sparse-to-dense crossover candidates from paired measurements.

This tool is decision support only. It never edits production thresholds. A
candidate requires dense to beat sparse by the requested median margin and to
avoid regressions on every paired seed for a configurable number of consecutive
measured cardinalities.
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path

FIELDS = {"representation", "operation", "cardinality", "repetitions", "seed", "ns_per_op", "result_size"}
OPERATIONS = {"intersection", "union", "contains", "materialize"}
REPRESENTATIONS = {"sparse", "dense"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Recommend MORPHEUS sparse-to-dense crossover candidates")
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("--output", type=Path, help="optional recommendation CSV")
    parser.add_argument("--margin-pct", type=float, default=5.0, help="minimum median dense speedup required")
    parser.add_argument("--consecutive", type=int, default=2, help="consecutive measured cardinalities that must satisfy the rule")
    parser.add_argument("--expect-samples", type=int, help="optional exact seed count per cardinality/operation")
    args = parser.parse_args()

    if not args.csv_file.is_file():
        parser.error(f"CSV not found: {args.csv_file}")
    if not math.isfinite(args.margin_pct) or args.margin_pct < 0 or args.margin_pct >= 100:
        parser.error("--margin-pct must be finite and in [0, 100)")
    if args.consecutive < 1:
        parser.error("--consecutive must be >= 1")
    if args.expect_samples is not None and args.expect_samples < 1:
        parser.error("--expect-samples must be >= 1")

    paired: dict[tuple[int, str, int], dict[str, float]] = defaultdict(dict)
    repetitions: dict[tuple[int, str, int], dict[str, int]] = defaultdict(dict)
    result_sizes: dict[tuple[int, str, int], dict[str, int]] = defaultdict(dict)
    cardinalities: set[int] = set()

    with args.csv_file.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if set(reader.fieldnames or ()) != FIELDS:
            parser.error(f"unexpected CSV fields: {reader.fieldnames!r}")
        for row_number, row in enumerate(reader, start=2):
            representation = row["representation"]
            operation = row["operation"]
            if representation not in REPRESENTATIONS or operation not in OPERATIONS:
                parser.error(f"unexpected topology on CSV row {row_number}")
            try:
                cardinality = int(row["cardinality"])
                repetition_count = int(row["repetitions"])
                seed = int(row["seed"])
                ns = float(row["ns_per_op"])
                result_size = int(row["result_size"])
            except (TypeError, ValueError) as exc:
                parser.error(f"invalid numeric field on CSV row {row_number}: {exc}")
            if cardinality < 1 or cardinality > 65536 or repetition_count < 1 or seed < 0 or seed > 0xFFFFFFFF:
                parser.error(f"invalid measurement metadata on CSV row {row_number}")
            if not math.isfinite(ns) or ns < 0 or result_size < 0:
                parser.error(f"invalid measurement value on CSV row {row_number}")

            key = (cardinality, operation, seed)
            if representation in paired[key]:
                parser.error(f"duplicate {representation} measurement for cardinality {cardinality}, {operation}, seed {seed}")
            paired[key][representation] = ns
            repetitions[key][representation] = repetition_count
            result_sizes[key][representation] = result_size
            cardinalities.add(cardinality)

    if not paired:
        parser.error("CSV contains no measurements")

    ratios: dict[tuple[int, str], list[float]] = defaultdict(list)
    for (cardinality, operation, seed), timings in paired.items():
        if set(timings) != REPRESENTATIONS:
            parser.error(f"missing sparse/dense pair for cardinality {cardinality}, {operation}, seed {seed}")
        if len(set(repetitions[(cardinality, operation, seed)].values())) != 1:
            parser.error(f"repetition mismatch for cardinality {cardinality}, {operation}, seed {seed}")
        if len(set(result_sizes[(cardinality, operation, seed)].values())) != 1:
            parser.error(f"result-size mismatch for cardinality {cardinality}, {operation}, seed {seed}")
        sparse_ns = timings["sparse"]
        dense_ns = timings["dense"]
        if sparse_ns == 0:
            ratio = math.inf if dense_ns > 0 else 1.0
        else:
            ratio = dense_ns / sparse_ns
        ratios[(cardinality, operation)].append(ratio)

    sorted_cardinalities = sorted(cardinalities)
    for cardinality in sorted_cardinalities:
        for operation in OPERATIONS:
            samples = ratios.get((cardinality, operation), [])
            if not samples:
                parser.error(f"missing paired measurements for cardinality {cardinality}, operation {operation}")
            if args.expect_samples is not None and len(samples) != args.expect_samples:
                parser.error(
                    f"expected {args.expect_samples} samples for cardinality {cardinality}, "
                    f"operation {operation}; got {len(samples)}"
                )

    target_ratio = 1.0 - (args.margin_pct / 100.0)
    output_rows: list[dict[str, object]] = []
    for operation in sorted(OPERATIONS):
        stable_points: list[int] = []
        candidate: int | None = None
        for cardinality in sorted_cardinalities:
            samples = ratios[(cardinality, operation)]
            median_ratio = statistics.median(samples)
            worst_ratio = max(samples)
            qualifies = math.isfinite(median_ratio) and median_ratio <= target_ratio and worst_ratio <= 1.0
            if qualifies:
                stable_points.append(cardinality)
                if len(stable_points) >= args.consecutive:
                    candidate = stable_points[-args.consecutive]
                    break
            else:
                stable_points.clear()

        if candidate is None:
            output_rows.append({
                "operation": operation,
                "candidate_cardinality": "",
                "status": "no_stable_candidate",
                "margin_pct": f"{args.margin_pct:.3f}",
                "consecutive_points": args.consecutive,
            })
        else:
            output_rows.append({
                "operation": operation,
                "candidate_cardinality": candidate,
                "status": "candidate",
                "margin_pct": f"{args.margin_pct:.3f}",
                "consecutive_points": args.consecutive,
            })

    fieldnames = ["operation", "candidate_cardinality", "status", "margin_pct", "consecutive_points"]
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        output_stream = args.output.open("w", newline="", encoding="utf-8")
    else:
        import sys
        output_stream = sys.stdout
    try:
        writer = csv.DictWriter(output_stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)
    finally:
        if args.output:
            output_stream.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
