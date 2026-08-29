from __future__ import annotations

from app.calibration_coverage import audit_workload_distribution_coverage
from app.catalog import PRIMITIVES
from app.models import (
    AccessDistribution,
    CalibrationMeasurement,
    CalibrationProfile,
    QueryDistributionSpec,
)
from app.parser import parse_workload_text


SPEC_TEXT = """
version: mws-0.1
name: coverage_workload
record_count: 1000
fields:
  - name: id
    type: uint64
    cardinality: 1000
queries:
  - kind: point_lookup
    field: id
    distribution:
      kind: hotspot
      hotspot_fraction: 0.1
      hotspot_probability: 0.8
  - kind: update
    distribution:
      kind: sequential
""".strip()


def _hotspot() -> QueryDistributionSpec:
    return QueryDistributionSpec(
        kind=AccessDistribution.HOTSPOT,
        hotspot_fraction=0.1,
        hotspot_probability=0.8,
    )


def _profile(measurements: list[CalibrationMeasurement], *, record_count: int = 1000) -> CalibrationProfile:
    return CalibrationProfile(
        id="coverage-distribution-profile",
        schema_version=4,
        evidence_state="MEASURED_LOCAL_PROCESS_REPEATED_IMPLEMENTATION_DISTRIBUTION_BOUND",
        protocol="morpheus-distribution-calibration-v1",
        record_count=record_count,
        operations=5000,
        seed=1337,
        machine={"cpu": "test"},
        measurements=measurements,
    )


def test_exact_workload_distribution_coverage_is_matched() -> None:
    implementation_id = PRIMITIVES["robin_hood_hash"].implementation_id
    profile = _profile(
        [
            CalibrationMeasurement(
                primitive="robin_hood_hash",
                implementation_id=implementation_id,
                operation="point_lookup",
                access_distribution=_hotspot(),
                ns_per_op=40.0,
            ),
            CalibrationMeasurement(
                primitive="robin_hood_hash",
                implementation_id=implementation_id,
                operation="update",
                access_distribution=QueryDistributionSpec(kind=AccessDistribution.SEQUENTIAL),
                ns_per_op=70.0,
            ),
        ]
    )
    report = audit_workload_distribution_coverage(
        profile,
        parse_workload_text(SPEC_TEXT),
        primitive_names=["robin_hood_hash"],
    )

    assert report.scale_matches_profile
    assert report.required_cells == 2
    assert report.matched_cells == 2
    assert report.coverage_ratio == 1.0
    assert all(cell.status == "MATCHED" for cell in report.cells)


def test_distribution_mismatch_is_not_counted_as_coverage() -> None:
    implementation_id = PRIMITIVES["robin_hood_hash"].implementation_id
    profile = _profile(
        [
            CalibrationMeasurement(
                primitive="robin_hood_hash",
                implementation_id=implementation_id,
                operation="point_lookup",
                access_distribution=QueryDistributionSpec(kind=AccessDistribution.UNIFORM),
                ns_per_op=40.0,
            ),
            CalibrationMeasurement(
                primitive="robin_hood_hash",
                implementation_id=implementation_id,
                operation="update",
                access_distribution=QueryDistributionSpec(kind=AccessDistribution.SEQUENTIAL),
                ns_per_op=70.0,
            ),
        ]
    )
    report = audit_workload_distribution_coverage(
        profile,
        parse_workload_text(SPEC_TEXT),
        primitive_names=["robin_hood_hash"],
    )
    statuses = {cell.operation: cell.status for cell in report.cells}
    assert statuses == {"point_lookup": "DISTRIBUTION_MISMATCH", "update": "MATCHED"}
    assert report.matched_cells == 1
    assert report.distribution_mismatch_cells == 1
    assert report.coverage_ratio == 0.5


def test_exact_measurement_at_wrong_scale_is_scale_mismatch() -> None:
    implementation_id = PRIMITIVES["robin_hood_hash"].implementation_id
    profile = _profile(
        [
            CalibrationMeasurement(
                primitive="robin_hood_hash",
                implementation_id=implementation_id,
                operation="point_lookup",
                access_distribution=_hotspot(),
                ns_per_op=40.0,
            ),
            CalibrationMeasurement(
                primitive="robin_hood_hash",
                implementation_id=implementation_id,
                operation="update",
                access_distribution=QueryDistributionSpec(kind=AccessDistribution.SEQUENTIAL),
                ns_per_op=70.0,
            ),
        ],
        record_count=5000,
    )
    report = audit_workload_distribution_coverage(
        profile,
        parse_workload_text(SPEC_TEXT),
        primitive_names=["robin_hood_hash"],
    )
    assert not report.scale_matches_profile
    assert report.matched_cells == 0
    assert report.scale_mismatch_cells == 2
    assert report.coverage_ratio == 0.0
    assert all(cell.status == "SCALE_MISMATCH" for cell in report.cells)


def test_stale_implementation_remains_fail_closed() -> None:
    profile = _profile(
        [
            CalibrationMeasurement(
                primitive="robin_hood_hash",
                implementation_id="morpheus.LegacyHash.v0",
                operation="point_lookup",
                access_distribution=_hotspot(),
                ns_per_op=30.0,
            )
        ]
    )
    report = audit_workload_distribution_coverage(
        profile,
        parse_workload_text(SPEC_TEXT),
        primitive_names=["robin_hood_hash"],
    )
    point = next(cell for cell in report.cells if cell.operation == "point_lookup")
    update = next(cell for cell in report.cells if cell.operation == "update")
    assert point.status == "STALE_ONLY"
    assert update.status == "MISSING"
    assert report.stale_only_cells == 1
    assert report.missing_cells == 1
