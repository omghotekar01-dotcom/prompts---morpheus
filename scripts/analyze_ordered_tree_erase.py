#!/usr/bin/env python3
"""Analyze MORPHEUS ordered-index erase measurements."""
from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path

FIELDS = {"implementation", "size", "erase_count", "repetitions", "seed", "ns_per_erase", "final_size", "checksum"}
IMPLEMENTATIONS = {"ordered_tree_rebuild", "bplus_tree_rebalanced", "std_map"}


def safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return math.inf if numerator > 0 else 1.0
    return numerator / denominator


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze MORPHEUS ordered-index erase benchmark CSV")
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
    checksums: dict[tuple[int, int], dict[str, int]] = defaultdict(dict)
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
                checksum = int(row["checksum"])
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
            if implementation in checksums[(size, seed)]:
                parser.error(f"duplicate result for size {size}, seed {seed}, implementation {implementation}")
            sizes.add(size)
            timings[key].append(ns)
            seeds[key].add(seed)
            erase_counts[key].add(erase_count)
            repetitions[key].add(repetition_count)
            checksums[(size, seed)][implementation] = checksum

    if not timings:
        parser.error("CSV contains no measurements")

    fields = [
        "size", "samples", "erase_count",
        "legacy_median_ns_per_erase", "rebalanced_median_ns_per_erase", "std_map_median_ns_per_erase",
        "rebalanced_over_legacy_ratio", "rebalanced_speedup_vs_legacy_pct",
        "rebalanced_over_std_map_ratio", "rebalanced_slowdown_vs_std_map_pct",
    ]
    output_rows: list[dict[str, object]] = []
    for size in sorted(sizes):
        reference_seeds: set[int] | None = None
        reference_erase_count: set[int] | None = None
        reference_repetitions: set[int] | None = None
        for implementation in IMPLEMENTATIONS:
            key = (size, implementation)
            if key not in timings:
                parser.error(f"missing measurements for size {size}, implementation {implementation}")
            if len(erase_counts[key]) != 1 or len(repetitions[key]) != 1:
                parser.error(f"inconsistent metadata for size {size}, implementation {implementation}")
            if args.expect_samples is not None and len(timings[key]) != args.expect_samples:
                parser.error(f"expected {args.expect_samples} samples for size {size}, implementation {implementation}")
            if reference_seeds is None:
                reference_seeds = seeds[key]
                reference_erase_count = erase_counts[key]
                reference_repetitions = repetitions[key]
            elif seeds[key] != reference_seeds or erase_counts[key] != reference_erase_count or repetitions[key] != reference_repetitions:
                parser.error(f"benchmark topology differs between implementations for size {size}")

        assert reference_seeds is not None and reference_erase_count is not None
        for seed in reference_seeds:
            by_implementation = checksums[(size, seed)]
            if set(by_implementation) != IMPLEMENTATIONS:
                parser.error(f"missing checksum topology for size {size}, seed {seed}")
            if len(set(by_implementation.values())) != 1:
                parser.error(f"result checksum differs between implementations for size {size}, seed {seed}")

        legacy = statistics.median(timings[(size, "ordered_tree_rebuild")])
        rebalanced = statistics.median(timings[(size, "bplus_tree_rebalanced")])
        std_map = statistics.median(timings[(size, "std_map")])
        rebalanced_over_legacy = safe_ratio(rebalanced, legacy)
        rebalanced_over_map = safe_ratio(rebalanced, std_map)
        speedup_vs_legacy = (1.0 - rebalanced_over_legacy) * 100.0 if math.isfinite(rebalanced_over_legacy) else float("-inf")
        slowdown_vs_map = (rebalanced_over_map - 1.0) * 100.0 if math.isfinite(rebalanced_over_map) else float("inf")
        output_rows.append({
            "size": size,
            "samples": len(timings[(size, "ordered_tree_rebuild")]),
            "erase_count": next(iter(reference_erase_count)),
            "legacy_median_ns_per_erase": f"{legacy:.3f}",
            "rebalanced_median_ns_per_erase": f"{rebalanced:.3f}",
            "std_map_median_ns_per_erase": f"{std_map:.3f}",
            "rebalanced_over_legacy_ratio": "inf" if not math.isfinite(rebalanced_over_legacy) else f"{rebalanced_over_legacy:.6f}",
            "rebalanced_speedup_vs_legacy_pct": "-inf" if not math.isfinite(speedup_vs_legacy) else f"{speedup_vs_legacy:.3f}",
            "rebalanced_over_std_map_ratio": "inf" if not math.isfinite(rebalanced_over_map) else f"{rebalanced_over_map:.6f}",
            "rebalanced_slowdown_vs_std_map_pct": "inf" if not math.isfinite(slowdown_vs_map) else f"{slowdown_vs_map:.3f}",
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
