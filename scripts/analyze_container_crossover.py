#!/usr/bin/env python3
"""Analyze MORPHEUS sparse-vs-dense container crossover measurements.

The output stays descriptive: it reports per-operation sparse/dense medians,
ratios and winners without automatically changing production thresholds.
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
    parser = argparse.ArgumentParser(description="Analyze MORPHEUS sparse-vs-dense bitmap container crossover CSV")
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("--output", type=Path, help="optional summary CSV")
    parser.add_argument("--expect-samples", type=int, help="require exactly this many seeds per cardinality/representation/operation")
    args = parser.parse_args()

    if args.expect_samples is not None and args.expect_samples < 1:
        parser.error("--expect-samples must be >= 1")
    if not args.csv_file.is_file():
        parser.error(f"CSV not found: {args.csv_file}")

    timings: dict[tuple[int, str, str], list[float]] = defaultdict(list)
    seeds: dict[tuple[int, str, str], set[int]] = defaultdict(set)
    repetitions: dict[tuple[int, str, str], set[int]] = defaultdict(set)
    result_sizes: dict[tuple[int, str, int], dict[str, int]] = defaultdict(dict)
    cardinalities: set[int] = set()

    with args.csv_file.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if set(reader.fieldnames or ()) != FIELDS:
            parser.error(f"unexpected CSV fields: {reader.fieldnames!r}")
        for row_number, row in enumerate(reader, start=2):
            representation = row["representation"]
            operation = row["operation"]
            if representation not in REPRESENTATIONS:
                parser.error(f"unexpected representation {representation!r} on CSV row {row_number}")
            if operation not in OPERATIONS:
                parser.error(f"unexpected operation {operation!r} on CSV row {row_number}")
            try:
                cardinality = int(row["cardinality"])
                repetition_count = int(row["repetitions"])
                seed = int(row["seed"])
                ns = float(row["ns_per_op"])
                result_size = int(row["result_size"])
            except (TypeError, ValueError) as exc:
                parser.error(f"invalid numeric field on CSV row {row_number}: {exc}")
            if cardinality < 1 or cardinality > 65536:
                parser.error(f"cardinality must be in [1, 65536] on CSV row {row_number}")
            if repetition_count < 1 or seed < 0 or seed > 0xFFFFFFFF or result_size < 0:
                parser.error(f"invalid measurement metadata on CSV row {row_number}")
            if not math.isfinite(ns) or ns < 0:
                parser.error(f"ns_per_op must be finite and non-negative on CSV row {row_number}")

            key = (cardinality, representation, operation)
            if seed in seeds[key]:
                parser.error(f"duplicate seed {seed} for cardinality {cardinality}, {representation}/{operation}")
            cardinalities.add(cardinality)
            timings[key].append(ns)
            seeds[key].add(seed)
            repetitions[key].add(repetition_count)
            result_sizes[(cardinality, operation, seed)][representation] = result_size

    if not timings:
        parser.error("CSV contains no measurements")

    for cardinality in sorted(cardinalities):
        reference_seeds: set[int] | None = None
        for representation in REPRESENTATIONS:
            for operation in OPERATIONS:
                key = (cardinality, representation, operation)
                if key not in timings:
                    parser.error(f"missing measurements for cardinality {cardinality}, {representation}/{operation}")
                if len(repetitions[key]) != 1:
                    parser.error(f"inconsistent repetitions for cardinality {cardinality}, {representation}/{operation}")
                if args.expect_samples is not None and len(timings[key]) != args.expect_samples:
                    parser.error(
                        f"expected {args.expect_samples} samples for cardinality {cardinality}, "
                        f"{representation}/{operation}; got {len(timings[key])}"
                    )
                if reference_seeds is None:
                    reference_seeds = seeds[key]
                elif seeds[key] != reference_seeds:
                    parser.error(f"seed topology differs at cardinality {cardinality}")

        assert reference_seeds is not None
        for operation in OPERATIONS:
            for seed in reference_seeds:
                by_representation = result_sizes[(cardinality, operation, seed)]
                if set(by_representation) != REPRESENTATIONS:
                    parser.error(f"missing result-size pair for cardinality {cardinality}, {operation}, seed {seed}")
                if by_representation["sparse"] != by_representation["dense"]:
                    parser.error(
                        f"sparse/dense result-size mismatch for cardinality {cardinality}, "
                        f"{operation}, seed {seed}: {by_representation}"
                    )

    fieldnames = [
        "cardinality", "operation", "samples", "sparse_median_ns_per_op", "dense_median_ns_per_op",
        "dense_over_sparse_ratio", "dense_speedup_pct", "winner",
    ]
    output_rows: list[dict[str, object]] = []
    for cardinality in sorted(cardinalities):
        for operation in sorted(OPERATIONS):
            sparse_values = timings[(cardinality, "sparse", operation)]
            dense_values = timings[(cardinality, "dense", operation)]
            sparse_median = statistics.median(sparse_values)
            dense_median = statistics.median(dense_values)
            if sparse_median == 0:
                ratio = math.inf if dense_median > 0 else 1.0
            else:
                ratio = dense_median / sparse_median
            speedup_pct = (1.0 - ratio) * 100.0 if math.isfinite(ratio) else float("-inf")
            if dense_median < sparse_median:
                winner = "dense"
            elif sparse_median < dense_median:
                winner = "sparse"
            else:
                winner = "tie"
            output_rows.append({
                "cardinality": cardinality,
                "operation": operation,
                "samples": len(sparse_values),
                "sparse_median_ns_per_op": f"{sparse_median:.3f}",
                "dense_median_ns_per_op": f"{dense_median:.3f}",
                "dense_over_sparse_ratio": "inf" if not math.isfinite(ratio) else f"{ratio:.6f}",
                "dense_speedup_pct": "-inf" if not math.isfinite(speedup_pct) else f"{speedup_pct:.3f}",
                "winner": winner,
            })

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
