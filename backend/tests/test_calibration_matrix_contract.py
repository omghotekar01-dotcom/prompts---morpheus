from __future__ import annotations

import importlib.util
from pathlib import Path

from app.catalog import PRIMITIVES


MODULE_PATH = Path(__file__).resolve().parents[2] / "benchmark" / "run_calibration_matrix.py"
SPEC = importlib.util.spec_from_file_location("morpheus_run_calibration_matrix", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_dependency_free_calibration_contract_matches_catalog() -> None:
    expected = {name: primitive.implementation_id for name, primitive in PRIMITIVES.items()}
    assert module.EXPECTED_IMPLEMENTATION_IDS == expected


def test_calibration_binding_validator_accepts_exact_catalog_identity() -> None:
    payload = {
        "measurements": [
            {
                "primitive": "ordered_tree",
                "implementation_id": PRIMITIVES["ordered_tree"].implementation_id,
                "operation": "point_lookup",
                "ns_per_op": 100.0,
            },
            {
                "primitive": "bitmap",
                "implementation_id": PRIMITIVES["bitmap"].implementation_id,
                "operation": "filter",
                "ns_per_op": 50.0,
            },
        ]
    }
    ids = module._validate_implementation_bindings(payload)
    assert ids == sorted(
        [PRIMITIVES["bitmap"].implementation_id, PRIMITIVES["ordered_tree"].implementation_id]
    )


def test_calibration_binding_validator_rejects_stale_identity() -> None:
    payload = {
        "measurements": [
            {
                "primitive": "ordered_tree",
                "implementation_id": "morpheus.OrderedTreeIndex.legacy",
                "operation": "point_lookup",
                "ns_per_op": 100.0,
            }
        ]
    }
    try:
        module._validate_implementation_bindings(payload)
    except RuntimeError as exc:
        assert "implementation mismatch" in str(exc)
    else:
        raise AssertionError("stale implementation identity must be rejected")
