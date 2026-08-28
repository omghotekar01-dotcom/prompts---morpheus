from __future__ import annotations

from app.calibration_coverage import audit_calibration_coverage, required_operations
from app.catalog import PRIMITIVES
from app.models import CalibrationMeasurement, CalibrationProfile


def _profile(measurements: list[CalibrationMeasurement]) -> CalibrationProfile:
    return CalibrationProfile(
        id="coverage-profile",
        schema_version=3,
        evidence_state="MEASURED_LOCAL_PROCESS_REPEATED_IMPLEMENTATION_BOUND",
        protocol="morpheus-calibration-v3",
        record_count=1000,
        operations=5000,
        seed=1337,
        machine={"cpu": "test"},
        measurements=measurements,
    )


def test_required_operations_reflect_generated_maintenance_contract() -> None:
    assert required_operations("bitmap") == ("build", "filter", "update")
    assert required_operations("sorted_array") == ("build", "point_lookup", "range_scan", "update")
    assert required_operations("csr_graph") == ("build", "graph_traversal")


def test_coverage_distinguishes_matched_stale_and_missing() -> None:
    bitmap_id = PRIMITIVES["bitmap"].implementation_id
    profile = _profile(
        [
            CalibrationMeasurement(
                primitive="bitmap",
                implementation_id=bitmap_id,
                operation="build",
                ns_per_op=20.0,
            ),
            CalibrationMeasurement(
                primitive="bitmap",
                implementation_id="morpheus.LegacyBitmap.v0",
                operation="filter",
                ns_per_op=10.0,
            ),
        ]
    )
    report = audit_calibration_coverage(profile, primitive_names=["bitmap"])
    assert report.required_cells == 3
    assert report.matched_cells == 1
    assert report.stale_only_cells == 1
    assert report.missing_cells == 1
    assert report.coverage_ratio == 1 / 3
    statuses = {cell.operation: cell.status for cell in report.cells}
    assert statuses == {"build": "MATCHED", "filter": "STALE_ONLY", "update": "MISSING"}


def test_full_single_primitive_coverage_is_one() -> None:
    implementation_id = PRIMITIVES["robin_hood_hash"].implementation_id
    profile = _profile(
        [
            CalibrationMeasurement(
                primitive="robin_hood_hash",
                implementation_id=implementation_id,
                operation=operation,
                ns_per_op=25.0,
            )
            for operation in required_operations("robin_hood_hash")
        ]
    )
    report = audit_calibration_coverage(profile, primitive_names=["robin_hood_hash"])
    assert report.coverage_ratio == 1.0
    assert report.missing_cells == 0
    assert report.stale_only_cells == 0
    assert all(cell.status == "MATCHED" for cell in report.cells)
