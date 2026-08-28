from __future__ import annotations

from app.cost_model import estimate_query_latency_us, estimate_update_us
from app.models import CalibrationMeasurement, CalibrationProfile, QueryKind
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


def _profile(implementation_id: str | None, *, record_count: int = 1000) -> CalibrationProfile:
    return CalibrationProfile(
        id="identity-test",
        schema_version=3,
        evidence_state="MEASURED_LOCAL_PROCESS_REPEATED_IMPLEMENTATION_BOUND",
        protocol="morpheus-calibration-v3",
        record_count=record_count,
        operations=5000,
        seed=1337,
        machine={"cpu": "test"},
        measurements=[
            CalibrationMeasurement(
                primitive="robin_hood_hash",
                implementation_id=implementation_id,
                operation="point_lookup",
                ns_per_op=10.0,
                repetitions=3,
            ),
            CalibrationMeasurement(
                primitive="robin_hood_hash",
                implementation_id=implementation_id,
                operation="update",
                ns_per_op=20.0,
                repetitions=3,
            ),
        ],
    )


def test_matching_implementation_id_and_scale_are_consumed() -> None:
    query = SPEC.queries[0]
    estimate = estimate_query_latency_us(
        SPEC,
        query,
        "robin_hood_hash",
        profile=_profile("morpheus.RobinHoodHashIndex.v1"),
    )
    assert estimate.source.startswith("CALIBRATED:identity-test:morpheus.RobinHoodHashIndex.v1:n=1000")
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
        profile=_profile(None),
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


def test_update_calibration_requires_explicit_matching_record_count() -> None:
    profile = _profile("morpheus.RobinHoodHashIndex.v1")

    missing_scale = estimate_update_us("robin_hood_hash", profile=profile)
    wrong_scale = estimate_update_us("robin_hood_hash", profile=profile, record_count=5000)
    matching_scale = estimate_update_us("robin_hood_hash", profile=profile, record_count=1000)

    assert missing_scale.source == "BOOTSTRAP_PRIOR"
    assert wrong_scale.source == "BOOTSTRAP_PRIOR"
    assert matching_scale.source.startswith(
        "CALIBRATED:identity-test:morpheus.RobinHoodHashIndex.v1:n=1000"
    )
    assert matching_scale.value == 0.02


def test_query_kind_contract_remains_point_lookup() -> None:
    assert SPEC.queries[0].kind == QueryKind.POINT_LOOKUP
