from __future__ import annotations

import importlib.util
from pathlib import Path

from app.catalog import PRIMITIVES


MODULE_PATH = Path(__file__).resolve().parents[2] / "benchmark" / "run_distribution_calibration_matrix.py"
SPEC = importlib.util.spec_from_file_location("morpheus_distribution_calibration_matrix", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_runner_implementation_ids_match_catalog() -> None:
    for primitive_name, implementation_id in module.EXPECTED_IMPLEMENTATION_IDS.items():
        assert PRIMITIVES[primitive_name].implementation_id == implementation_id


def test_payload_contract_requires_exact_distribution_coverage_and_parameters() -> None:
    payload = {
        "schema_version": 4,
        "protocol": "morpheus-distribution-calibration-v1",
        "distribution_protocol": "morpheus-access-distribution-v1",
        "measurements": [
            {
                "primitive": "robin_hood_hash",
                "implementation_id": "morpheus.RobinHoodHashIndex.v1",
                "operation": "point_lookup",
                "access_distribution": {"kind": "uniform"},
                "ns_per_op": 10.0,
            },
            {
                "primitive": "robin_hood_hash",
                "implementation_id": "morpheus.RobinHoodHashIndex.v1",
                "operation": "point_lookup",
                "access_distribution": {"kind": "hotspot", "hotspot_fraction": 0.1, "hotspot_probability": 0.8},
                "ns_per_op": 8.0,
            },
            {
                "primitive": "robin_hood_hash",
                "implementation_id": "morpheus.RobinHoodHashIndex.v1",
                "operation": "point_lookup",
                "access_distribution": {"kind": "zipf", "zipf_theta": 0.99},
                "ns_per_op": 7.0,
            },
            {
                "primitive": "robin_hood_hash",
                "implementation_id": "morpheus.RobinHoodHashIndex.v1",
                "operation": "point_lookup",
                "access_distribution": {"kind": "sequential"},
                "ns_per_op": 6.0,
            },
        ],
    }
    result = module._validate_payload(payload, {"uniform", "hotspot", "zipf", "sequential"})
    assert result["measurement_count"] == 4
    assert result["distributions"] == ["hotspot", "sequential", "uniform", "zipf"]


def test_runner_rejects_missing_hotspot_parameters() -> None:
    payload = {
        "schema_version": 4,
        "protocol": "morpheus-distribution-calibration-v1",
        "distribution_protocol": "morpheus-access-distribution-v1",
        "measurements": [
            {
                "primitive": "robin_hood_hash",
                "implementation_id": "morpheus.RobinHoodHashIndex.v1",
                "operation": "point_lookup",
                "access_distribution": {"kind": "hotspot"},
                "ns_per_op": 8.0,
            }
        ],
    }
    try:
        module._validate_payload(payload, {"hotspot"})
    except RuntimeError as exc:
        assert "hotspot parameters" in str(exc)
    else:
        raise AssertionError("missing hotspot parameters must fail closed")
