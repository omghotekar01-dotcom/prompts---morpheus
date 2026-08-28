from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_DIR = REPO_ROOT / "benchmark"
if str(BENCHMARK_DIR) not in sys.path:
    sys.path.insert(0, str(BENCHMARK_DIR))

from analyze_calibration_surface import analyze_calibration_matrix, log_interpolate  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_matrix(root: Path) -> Path:
    matrix = root / "matrix"
    matrix.mkdir()
    runs = []
    implementation_id = "morpheus.RobinHoodHashIndex.v1"
    values = {
        100: [10.0, 10.0],
        1000: [31.0, 32.0],
        10000: [100.0, 100.0],
    }
    for record_count, samples in values.items():
        for seed_index, value in enumerate(samples, start=1):
            seed = 1000 + seed_index
            file_name = f"calibration-n{record_count}-seed{seed}.json"
            path = matrix / file_name
            payload = {
                "profile_id": f"fixture-{record_count}-{seed}",
                "schema_version": 3,
                "protocol": "morpheus-calibration-v3",
                "evidence_state": "MEASURED_LOCAL_PROCESS_REPEATED_IMPLEMENTATION_BOUND",
                "n": record_count,
                "operations": 1000,
                "seed": seed,
                "measurements": [
                    {
                        "primitive": "robin_hood_hash",
                        "implementation_id": implementation_id,
                        "operation": "point_lookup",
                        "ns_per_op": value,
                    }
                ],
            }
            path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
            runs.append(
                {
                    "file": file_name,
                    "sha256": _sha256(path),
                    "record_count": record_count,
                    "seed": seed,
                    "protocol": "morpheus-calibration-v3",
                }
            )

    manifest = {
        "schema_version": 2,
        "protocol": "morpheus-calibration-matrix-v2",
        "source_commit": "a" * 40,
        "executable_sha256": "b" * 64,
        "machine_fingerprint_sha256": "c" * 64,
        "implementation_ids": [implementation_id],
        "runs": runs,
    }
    (matrix / "manifest.json").write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    return matrix


def test_log_interpolation_matches_power_law_and_refuses_extrapolation() -> None:
    predicted = log_interpolate(1000, 100, 10.0, 10000, 100.0)
    assert predicted == pytest.approx(math.sqrt(1000), rel=1e-12)

    with pytest.raises(ValueError, match="extrapolation is forbidden"):
        log_interpolate(100000, 100, 10.0, 10000, 100.0)


def test_surface_evaluator_holds_out_only_interior_measured_scale(tmp_path: Path) -> None:
    matrix = _write_matrix(tmp_path)
    report = analyze_calibration_matrix(matrix)

    assert report["protocol"] == "morpheus-calibration-surface-evaluation-v1"
    assert report["machine_fingerprint_sha256"] == "c" * 64
    assert report["eligible_for_optimizer_automatic_promotion"] is False
    assert report["metrics"]["holdout_count"] == 1
    assert len(report["holdouts"]) == 1
    holdout = report["holdouts"][0]
    assert holdout["target_record_count"] == 1000
    assert holdout["lower_record_count"] == 100
    assert holdout["upper_record_count"] == 10000
    assert holdout["predicted_ns_per_op"] == pytest.approx(math.sqrt(1000), rel=1e-12)
    assert holdout["absolute_percentage_error"] < 0.01
    assert "never extrapolates" in report["truth_boundary"]


def test_surface_evaluator_rejects_tampered_measurement_artifact(tmp_path: Path) -> None:
    matrix = _write_matrix(tmp_path)
    target = next(matrix.glob("calibration-n1000-*.json"))
    target.write_text(target.read_text(encoding="utf-8") + " ", encoding="utf-8")

    with pytest.raises(ValueError, match="hash mismatch"):
        analyze_calibration_matrix(matrix)
