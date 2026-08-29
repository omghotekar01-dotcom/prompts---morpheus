from __future__ import annotations

from app.cost_model import estimate_query_latency_us, estimate_update_us
from app.models import (
    AccessDistribution,
    CalibrationMeasurement,
    CalibrationProfile,
    QueryDistributionSpec,
    QueryKind,
)
from app.parser import parse_workload_text


SPEC = parse_workload_text(
    """
version: mws-0.1
name: calibration_identity
record_count: 1000
fields:
  - name: id
    type: uint64
    cardinality: 1000
queries:
  - kind: point_lookup
    field: id
""".strip()
)

UNIFORM = QueryDistributionSpec(kind=AccessDistribution.UNIFORM)
HOTSPOT = QueryDistributionSpec(
    kind=AccessDistribution.HOTSPOT,
    hotspot_fraction=0.1,
    hotspot_probability=0.8,
)


def _profile(
    implementation_id: str | None,
    *,
    record_count: int = 1000,
    distribution: QueryDistributionSpec | None = UNIFORM,
) -> CalibrationProfile:
    return CalibrationProfile(
        id="identity-test",
        schema_version=4,
        evidence_state="MEASURED_LOCAL_PROCESS_REPEATED_IMPLEMENTATION_AND_DISTRIBUTION_BOUND",
        protocol="morpheus-distribution-calibration-v1",
        record_count=record_count,
        operations=5000,
        seed=1337,
        machine={"cpu": "test"},
        measurements=[
            CalibrationMeasurement(
                primitive="robin_hood_hash",
                implementation_id=implementation_id,
                operation="point_lookup",
                access_distribution=distribution,
                ns_per_op=10.0,
                repetitions=3,
            ),
            CalibrationMeasurement(
                primitive="robin_hood_hash",
                implementation_id=implementation_id,
                operation="update",
                access_distribution=distribution,
                ns_per_op=20.0,
                repetitions=3,
            ),
        ],
    )


def test_matching_implementation_scale_and_distribution_are_consumed() -> None:
    query = SPEC.queries[0]
    estimate = estimate_query_latency_us(
        SPEC,
        query,
        "robin_hood_hash",
        profile=_profile("morpheus.RobinHoodHashIndex.v1"),
    )
    assert estimate.source.startswith("CALIBRATED:identity-test:morpheus.RobinHoodHashIndex.v1:n=1000:dist=uniform")
    assert estimate.value == 0.01


def test_stale_implementation_id_falls_back_to_bootstrap_prior() -> None:
    query = SPEC.queries[0]
    estimate = estimate_query_latency_us(
        SPEC,
        query,
        "robin_hood_hash",
        profile=_profile("morpheus.LegacyHash.v0"),
    )
    assert estimate.source == "BOOTSTRAP_PRIOR"
    assert estimate.uncertainty_ratio == 0.50


def test_unlabeled_legacy_measurement_is_not_silently_promoted() -> None:
    query = SPEC.queries[0]
    estimate = estimate_query_latency_us(
        SPEC,
        query,
        "robin_hood_hash",
        profile=_profile("morpheus.RobinHoodHashIndex.v1", distribution=None),
    )
    assert estimate.source == "BOOTSTRAP_PRIOR"


def test_matching_implementation_at_different_record_count_is_not_called_calibrated() -> None:
    query = SPEC.queries[0]
    estimate = estimate_query_latency_us(
        SPEC,
        query,
        "robin_hood_hash",
        profile=_profile("morpheus.RobinHoodHashIndex.v1", record_count=5000),
    )
    assert estimate.source == "BOOTSTRAP_PRIOR"
    assert estimate.uncertainty_ratio == 0.50


def test_distribution_mismatch_is_not_consumed() -> None:
    query = SPEC.queries[0]
    estimate = estimate_query_latency_us(
        SPEC,
        query,
        "robin_hood_hash",
        profile=_profile("morpheus.RobinHoodHashIndex.v1", distribution=HOTSPOT),
    )
    assert estimate.source == "BOOTSTRAP_PRIOR"


def test_update_calibration_requires_scale_and_distribution() -> None:
    profile = _profile("morpheus.RobinHoodHashIndex.v1")

    missing_distribution = estimate_update_us("robin_hood_hash", profile=profile, record_count=1000)
    wrong_scale = estimate_update_us(
        "robin_hood_hash",
        profile=profile,
        record_count=5000,
        distribution=UNIFORM,
    )
    matching = estimate_update_us(
        "robin_hood_hash",
        profile=profile,
        record_count=1000,
        distribution=UNIFORM,
    )

    assert missing_distribution.source == "BOOTSTRAP_PRIOR"
    assert wrong_scale.source == "BOOTSTRAP_PRIOR"
    assert matching.source.startswith(
        "CALIBRATED:identity-test:morpheus.RobinHoodHashIndex.v1:n=1000:dist=uniform"
    )
    assert matching.value == 0.02


def test_hotspot_parameters_are_part_of_identity() -> None:
    hotspot_spec = parse_workload_text(
        """
version: mws-0.1
name: hotspot
record_count: 1000
fields:
  - name: id
    type: uint64
queries:
  - kind: point_lookup
    field: id
    distribution:
      kind: hotspot
      hotspot_fraction: 0.1
      hotspot_probability: 0.9
""".strip()
    )
    estimate = estimate_query_latency_us(
        hotspot_spec,
        hotspot_spec.queries[0],
        "robin_hood_hash",
        profile=_profile("morpheus.RobinHoodHashIndex.v1", distribution=HOTSPOT),
    )
    assert estimate.source.startswith("BOOTSTRAP_PRIOR_DISTRIBUTION_UNMODELED:hotspot")
    assert estimate.uncertainty_ratio == 0.80


def test_query_kind_contract_remains_point_lookup() -> None:
    assert SPEC.queries[0].kind == QueryKind.POINT_LOOKUP
