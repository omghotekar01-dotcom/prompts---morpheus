#!/usr/bin/env python3
"""Summarize MORPHEUS adaptive-bitmap sweep CSV without overstating conclusions.

Consumes normalized output from sweep_bitmap_benchmark.py, aggregates repeated
seeds, and reports medians plus spread. The report is evidence for threshold
review; it does not automatically rewrite production thresholds.
"""
from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

REQUIRED = {"operation", "cardinality", "repetitions", "seed", "dense_containers", "ns_per_op", "result_size"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze MORPHEUS bitmap sweep CSV")
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("--output", type=Path, help="optional summary CSV")
    args = parser.parse_args()

    if not args.csv_file.is_file():
        parser.error(f"CSV not found: {args.csv_file}")

    grouped: dict[tuple[int, str], list[float]] = defaultdict(list)
    dense: dict[tuple[int, str], list[int]] = defaultdict(list)
    with args.csv_file.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if set(reader.fieldnames or ()) != REQUIRED:
            parser.error(f"unexpected CSV fields: {reader.fieldnames!r}")
        for row in reader:
            cardinality = int(row["cardinality"])
            operation = row["operation"]
            ns = float(row["ns_per_op"])
            if cardinality < 1 or ns < 0:
                parser.error("invalid negative/zero measurement metadata")
            key = (cardinality, operation)
            grouped[key].append(ns)
            dense[key].append(int(row["dense_containers"]))

    if not grouped:
        parser.error("CSV contains no measurements")

    fields = ["cardinality", "operation", "samples", "median_ns_per_op", "min_ns_per_op", "max_ns_per_op", "median_dense_containers"]
    output_rows = []
    for key in sorted(grouped):
        values = grouped[key]
        output_rows.append({
            "cardinality": key[0],
            "operation": key[1],
            "samples": len(values),
            "median_ns_per_op": f"{statistics.median(values):.3f}",
            "min_ns_per_op": f"{min(values):.3f}",
            "max_ns_per_op": f"{max(values):.3f}",
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
