#!/usr/bin/env python3
"""Analyze MORPHEUS OrderedTreeIndex erase baseline measurements."""
from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path

FIELDS = {"implementation", "size", "erase_count", "repetitions", "seed", "ns_per_erase", "final_size", "checksum"}
IMPLEMENTATIONS = {"ordered_tree_rebuild", "std_map"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze MORPHEUS OrderedTreeIndex erase benchmark CSV")
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("--output", type=Path, help="optional summary CSV")
    parser.add_argument("--expect-samples", type=int, help="require exact seed count per size/implementation")
    args = parser.parse_args()

    if not args.csv_file.is_file():
        parser.error(f"CSV not found: {args.csv_file}")
    if args.expect_samples is not None and args.expect_samples < 1:
        parser.error("--expect-samples must be >= 1")

    timings: dict[tuple[int, str], list[float]] = defaultdict(list)
    seeds: dict[tuple[int, str], set[int]] = defaultdict(set)
    erase_counts: dict[tuple[int, str], set[int]] = defaultdict(set)
    repetitions: dict[tuple[int, str], set[int]] = defaultdict(set)
    sizes: set[int] = set()

    with args.csv_file.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if set(reader.fieldnames or ()) != FIELDS:
            parser.error(f"unexpected CSV fields: {reader.fieldnames!r}")
        for row_number, row in enumerate(reader, start=2):
            implementation = row["implementation"]
            if implementation not in IMPLEMENTATIONS:
                parser.error(f"unexpected implementation {implementation!r} on row {row_number}")
            try:
                size = int(row["size"])
                erase_count = int(row["erase_count"])
                repetition_count = int(row["repetitions"])
                seed = int(row["seed"])
                ns = float(row["ns_per_erase"])
                final_size = int(row["final_size"])
                int(row["checksum"])
            except (TypeError, ValueError) as exc:
                parser.error(f"invalid numeric field on row {row_number}: {exc}")
            if size < 2 or erase_count < 1 or erase_count >= size or repetition_count < 1 or seed < 0 or seed > 0xFFFFFFFF:
                parser.error(f"invalid metadata on row {row_number}")
            if final_size != size - erase_count:
                parser.error(f"final-size mismatch on row {row_number}")
            if not math.isfinite(ns) or ns < 0:
                parser.error(f"invalid timing on row {row_number}")

            key = (size, implementation)
            if seed in seeds[key]:
                parser.error(f"duplicate seed {seed} for size {size}, implementation {implementation}")
            sizes.add(size)
            timings[key].append(ns)
            seeds[key].add(seed)
            erase_counts[key].add(erase_count)
            repetitions[key].add(repetition_count)

    if not timings:
        parser.error("CSV contains no measurements")

    fields = [
        "size", "samples", "erase_count", "ordered_tree_median_ns_per_erase", "std_map_median_ns_per_erase",
        "ordered_over_std_map_ratio", "ordered_slowdown_pct",
    ]
    output_rows: list[dict[str, object]] = []
    for size in sorted(sizes):
        for implementation in IMPLEMENTATIONS:
            key = (size, implementation)
            if key not in timings:
                parser.error(f"missing measurements for size {size}, implementation {implementation}")
            if len(erase_counts[key]) != 1 or len(repetitions[key]) != 1:
                parser.error(f"inconsistent metadata for size {size}, implementation {implementation}")
            if args.expect_samples is not None and len(timings[key]) != args.expect_samples:
                parser.error(f"expected {args.expect_samples} samples for size {size}, implementation {implementation}")

        ordered_key = (size, "ordered_tree_rebuild")
        map_key = (size, "std_map")
        if seeds[ordered_key] != seeds[map_key]:
            parser.error(f"seed topology differs between implementations for size {size}")
        if erase_counts[ordered_key] != erase_counts[map_key] or repetitions[ordered_key] != repetitions[map_key]:
            parser.error(f"benchmark metadata differs between implementations for size {size}")

        ordered_median = statistics.median(timings[ordered_key])
        map_median = statistics.median(timings[map_key])
        ratio = math.inf if map_median == 0 and ordered_median > 0 else (1.0 if map_median == 0 else ordered_median / map_median)
        slowdown = math.inf if not math.isfinite(ratio) else (ratio - 1.0) * 100.0
        output_rows.append({
            "size": size,
            "samples": len(timings[ordered_key]),
            "erase_count": next(iter(erase_counts[ordered_key])),
            "ordered_tree_median_ns_per_erase": f"{ordered_median:.3f}",
            "std_map_median_ns_per_erase": f"{map_median:.3f}",
            "ordered_over_std_map_ratio": "inf" if not math.isfinite(ratio) else f"{ratio:.6f}",
            "ordered_slowdown_pct": "inf" if not math.isfinite(slowdown) else f"{slowdown:.3f}",
        })

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        output_stream = args.output.open("w", newline="", encoding="utf-8")
    else:
        import sys
        output_stream = sys.stdout
    try:
        writer = csv.DictWriter(output_stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)
    finally:
        if args.output:
            output_stream.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
