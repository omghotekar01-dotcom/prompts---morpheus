from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


EXPECTED_MATRIX_PROTOCOL = "morpheus-calibration-matrix-v2"
EXPECTED_RUN_PROTOCOL = "morpheus-calibration-v3"
EVIDENCE_STATE = "LEAVE_ONE_INTERIOR_SCALE_OUT_INTERPOLATION_EVALUATION_ON_SAME_MACHINE_MATRIX"


@dataclass(frozen=True)
class CellKey:
    primitive: str
    implementation_id: str
    operation: str

    def as_dict(self) -> dict[str, str]:
        return {
            "primitive": self.primitive,
            "implementation_id": self.implementation_id,
            "operation": self.operation,
        }


@dataclass(frozen=True)
class SizeAggregate:
    record_count: int
    sample_count: int
    median_ns_per_op: float
    min_ns_per_op: float
    max_ns_per_op: float
    relative_mad: float

    def as_dict(self) -> dict[str, object]:
        return {
            "record_count": self.record_count,
            "sample_count": self.sample_count,
            "median_ns_per_op": self.median_ns_per_op,
            "min_ns_per_op": self.min_ns_per_op,
            "max_ns_per_op": self.max_ns_per_op,
            "relative_mad": self.relative_mad,
        }


@dataclass(frozen=True)
class HoldoutPoint:
    cell: CellKey
    target_record_count: int
    lower_record_count: int
    upper_record_count: int
    measured_ns_per_op: float
    predicted_ns_per_op: float
    absolute_error_ns: float
    absolute_percentage_error: float
    log_error: float

    def as_dict(self) -> dict[str, object]:
        return {
            **self.cell.as_dict(),
            "target_record_count": self.target_record_count,
            "lower_record_count": self.lower_record_count,
            "upper_record_count": self.upper_record_count,
            "measured_ns_per_op": self.measured_ns_per_op,
            "predicted_ns_per_op": self.predicted_ns_per_op,
            "absolute_error_ns": self.absolute_error_ns,
            "absolute_percentage_error": self.absolute_percentage_error,
            "log_error": self.log_error,
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _median(values: Iterable[float]) -> float:
    data = list(values)
    if not data:
        raise ValueError("median requires at least one value")
    return float(statistics.median(data))


def _relative_mad(values: list[float], median: float) -> float:
    if median <= 0:
        raise ValueError("calibration median must be positive")
    mad = _median(abs(value - median) for value in values)
    return mad / median


def log_interpolate(
    target_record_count: int,
    lower_record_count: int,
    lower_ns_per_op: float,
    upper_record_count: int,
    upper_ns_per_op: float,
) -> float:
    """Interpolate positive cost in log(record_count)-log(cost) space.

    Extrapolation is intentionally forbidden. This function is a research
    evaluator, not an optimizer-side permission slip.
    """

    if min(target_record_count, lower_record_count, upper_record_count) <= 0:
        raise ValueError("record counts must be positive")
    if lower_record_count >= upper_record_count:
        raise ValueError("lower_record_count must be smaller than upper_record_count")
    if not lower_record_count <= target_record_count <= upper_record_count:
        raise ValueError("calibration surface extrapolation is forbidden")
    if lower_ns_per_op <= 0 or upper_ns_per_op <= 0:
        raise ValueError("latency anchors must be positive")
    if target_record_count == lower_record_count:
        return lower_ns_per_op
    if target_record_count == upper_record_count:
        return upper_ns_per_op

    low_x = math.log(float(lower_record_count))
    high_x = math.log(float(upper_record_count))
    target_x = math.log(float(target_record_count))
    weight = (target_x - low_x) / (high_x - low_x)
    predicted_log = math.log(lower_ns_per_op) + weight * (
        math.log(upper_ns_per_op) - math.log(lower_ns_per_op)
    )
    return math.exp(predicted_log)


def _load_matrix(matrix_dir: Path) -> tuple[dict[str, Any], dict[CellKey, dict[int, list[float]]]]:
    manifest_path = matrix_dir / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"missing calibration manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("protocol") != EXPECTED_MATRIX_PROTOCOL:
        raise ValueError(
            f"expected {EXPECTED_MATRIX_PROTOCOL}, got {manifest.get('protocol')!r}"
        )
    machine_fingerprint = manifest.get("machine_fingerprint_sha256")
    if not isinstance(machine_fingerprint, str) or len(machine_fingerprint) != 64:
        raise ValueError("calibration matrix requires a 64-character machine fingerprint")
    runs = manifest.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError("calibration manifest must contain non-empty runs")

    by_cell: dict[CellKey, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    for run_index, run in enumerate(runs):
        if not isinstance(run, dict):
            raise ValueError(f"manifest run[{run_index}] must be an object")
        file_name = run.get("file")
        expected_hash = run.get("sha256")
        if not isinstance(file_name, str) or not file_name:
            raise ValueError(f"manifest run[{run_index}] lacks file")
        path = matrix_dir / file_name
        if not path.is_file():
            raise ValueError(f"missing calibration run file: {path}")
        if not isinstance(expected_hash, str) or _sha256(path) != expected_hash:
            raise ValueError(f"calibration run hash mismatch: {file_name}")

        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("protocol") != EXPECTED_RUN_PROTOCOL:
            raise ValueError(f"run {file_name} is not {EXPECTED_RUN_PROTOCOL}")
        record_count = int(payload.get("n", run.get("record_count", 0)))
        if record_count <= 0:
            raise ValueError(f"run {file_name} has invalid record count")
        if int(run.get("record_count", record_count)) != record_count:
            raise ValueError(f"run {file_name} manifest/payload record-count mismatch")
        measurements = payload.get("measurements")
        if not isinstance(measurements, list) or not measurements:
            raise ValueError(f"run {file_name} has no measurements")
        seen: set[CellKey] = set()
        for measurement in measurements:
            if not isinstance(measurement, dict):
                raise ValueError(f"run {file_name} contains a non-object measurement")
            key = CellKey(
                primitive=str(measurement.get("primitive", "")),
                implementation_id=str(measurement.get("implementation_id", "")),
                operation=str(measurement.get("operation", "")),
            )
            if not key.primitive or not key.implementation_id or not key.operation:
                raise ValueError(f"run {file_name} contains an unlabeled measurement")
            if key in seen:
                raise ValueError(f"run {file_name} duplicates cell {key}")
            seen.add(key)
            value = float(measurement.get("ns_per_op", 0.0))
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"run {file_name} cell {key} has invalid ns_per_op")
            by_cell[key][record_count].append(value)

    return manifest, by_cell


def _aggregate_sizes(values_by_size: dict[int, list[float]]) -> dict[int, SizeAggregate]:
    aggregates: dict[int, SizeAggregate] = {}
    for record_count in sorted(values_by_size):
        values = values_by_size[record_count]
        median = _median(values)
        aggregates[record_count] = SizeAggregate(
            record_count=record_count,
            sample_count=len(values),
            median_ns_per_op=median,
            min_ns_per_op=min(values),
            max_ns_per_op=max(values),
            relative_mad=_relative_mad(values, median),
        )
    return aggregates


def _holdout_points(cell: CellKey, aggregates: dict[int, SizeAggregate]) -> list[HoldoutPoint]:
    sizes = sorted(aggregates)
    points: list[HoldoutPoint] = []
    # Only an interior measured scale can be predicted without extrapolation
    # after withholding that scale. Endpoints are deliberately not evaluated.
    for index in range(1, len(sizes) - 1):
        target = sizes[index]
        lower = sizes[index - 1]
        upper = sizes[index + 1]
        measured = aggregates[target].median_ns_per_op
        predicted = log_interpolate(
            target,
            lower,
            aggregates[lower].median_ns_per_op,
            upper,
            aggregates[upper].median_ns_per_op,
        )
        absolute_error = abs(predicted - measured)
        points.append(
            HoldoutPoint(
                cell=cell,
                target_record_count=target,
                lower_record_count=lower,
                upper_record_count=upper,
                measured_ns_per_op=measured,
                predicted_ns_per_op=predicted,
                absolute_error_ns=absolute_error,
                absolute_percentage_error=absolute_error / measured,
                log_error=abs(math.log(predicted) - math.log(measured)),
            )
        )
    return points


def analyze_calibration_matrix(matrix_dir: Path) -> dict[str, Any]:
    manifest, by_cell = _load_matrix(matrix_dir)
    cells: list[dict[str, Any]] = []
    holdouts: list[HoldoutPoint] = []
    skipped_cells: list[dict[str, Any]] = []

    for cell in sorted(by_cell, key=lambda item: (item.primitive, item.operation, item.implementation_id)):
        aggregates = _aggregate_sizes(by_cell[cell])
        if len(aggregates) < 3:
            skipped_cells.append(
                {
                    **cell.as_dict(),
                    "reason": "fewer_than_three_distinct_measured_scales",
                    "measured_scales": sorted(aggregates),
                }
            )
            continue
        cell_holdouts = _holdout_points(cell, aggregates)
        holdouts.extend(cell_holdouts)
        cells.append(
            {
                **cell.as_dict(),
                "anchors": [aggregates[size].as_dict() for size in sorted(aggregates)],
                "interior_holdout_count": len(cell_holdouts),
            }
        )

    if holdouts:
        absolute_errors = [point.absolute_error_ns for point in holdouts]
        percentage_errors = [point.absolute_percentage_error for point in holdouts]
        log_errors = [point.log_error for point in holdouts]
        metrics: dict[str, Any] = {
            "holdout_count": len(holdouts),
            "mae_ns": sum(absolute_errors) / len(absolute_errors),
            "median_absolute_error_ns": _median(absolute_errors),
            "mape": sum(percentage_errors) / len(percentage_errors),
            "median_absolute_percentage_error": _median(percentage_errors),
            "rms_log_error": math.sqrt(sum(value * value for value in log_errors) / len(log_errors)),
            "fraction_within_10_percent": sum(value <= 0.10 for value in percentage_errors) / len(percentage_errors),
            "fraction_within_20_percent": sum(value <= 0.20 for value in percentage_errors) / len(percentage_errors),
            "fraction_within_50_percent": sum(value <= 0.50 for value in percentage_errors) / len(percentage_errors),
        }
    else:
        metrics = {
            "holdout_count": 0,
            "mae_ns": None,
            "median_absolute_error_ns": None,
            "mape": None,
            "median_absolute_percentage_error": None,
            "rms_log_error": None,
            "fraction_within_10_percent": None,
            "fraction_within_20_percent": None,
            "fraction_within_50_percent": None,
        }

    return {
        "schema_version": 1,
        "protocol": "morpheus-calibration-surface-evaluation-v1",
        "source_matrix_protocol": manifest.get("protocol"),
        "source_commit": manifest.get("source_commit"),
        "source_executable_sha256": manifest.get("executable_sha256"),
        "machine_fingerprint_sha256": manifest.get("machine_fingerprint_sha256"),
        "implementation_ids": manifest.get("implementation_ids", []),
        "evidence_state": EVIDENCE_STATE,
        "eligible_for_optimizer_automatic_promotion": False,
        "metrics": metrics,
        "cells": cells,
        "holdouts": [point.as_dict() for point in holdouts],
        "skipped_cells": skipped_cells,
        "truth_boundary": (
            "This report evaluates log-space interpolation only at measured interior record-count scales, on the same machine fingerprint and exact implementation IDs. "
            "It never extrapolates beyond measured scales, does not measure generated composite artifacts, and does not automatically authorize optimizer use. "
            "Independent held-out workload and generated-candidate validation remain required before any performance claim or automatic model promotion."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate same-machine implementation-bound calibration interpolation by leaving out interior measured scales."
        )
    )
    parser.add_argument("matrix_dir", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    matrix_dir = args.matrix_dir.resolve()
    report = analyze_calibration_matrix(matrix_dir)
    output = args.output.resolve() if args.output is not None else matrix_dir / "calibration-surface-evaluation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
