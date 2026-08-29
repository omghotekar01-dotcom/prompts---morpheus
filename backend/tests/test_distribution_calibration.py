from __future__ import annotations

import pytest

from app.calibration import profile_from_smoke_payload
from app.cost_model import estimate_query_latency_us
from app.models import CalibrationMeasurement
from app.parser import parse_workload_text


def _payload(distribution: dict[str, object]) -> dict[str, object]:
    return {
        "profile_id": "dist-lab",
        "schema_version": 4,
        "evidence_state": "MEASURED_LOCAL_PROCESS_REPEATED_IMPLEMENTATION_AND_DISTRIBUTION_BOUND",
        "protocol": "morpheus-distribution-calibration-v1",
        "distribution_protocol": "morpheus-access-distribution-v1",
        "n": 1000,
        "operations": 5000,
        "seed": 1337,
        "machine": {"compiler": "test"},
        "measurements": [
            {
                "primitive": "robin_hood_hash",
                "implementation_id": "morpheus.RobinHoodHashIndex.v1",
                "operation": "point_lookup",
                "access_distribution": distribution,
                "ns_per_op": 25.0,
                "repetitions": 3,
                "stdev_ns": 1.0,
            }
        ],
    }


def _spec(distribution_yaml: str) -> object:
    return parse_workload_text(
        f"""
version: mws-0.1
name: distribution-calibration
record_count: 1000
fields:
  - name: id
    type: uint64
queries:
  - kind: point_lookup
    field: id
    distribution:
{distribution_yaml}
""".strip()
    )


def test_exact_hotspot_parameters_are_consumed() -> None:
    profile = profile_from_smoke_payload(
        _payload({"kind": "hotspot", "hotspot_fraction": 0.1, "hotspot_probability": 0.8})
    )
    spec = _spec("      kind: hotspot\n      hotspot_fraction: 0.1\n      hotspot_probability: 0.8")
    estimate = estimate_query_latency_us(spec, spec.queries[0], "robin_hood_hash", profile=profile)
    assert estimate.value == 0.025
    assert "dist=hotspot(f=0.1,p=0.8)" in estimate.source
    assert estimate.uncertainty_ratio < 0.5


def test_same_distribution_kind_with_different_parameter_is_rejected() -> None:
    profile = profile_from_smoke_payload(
        _payload({"kind": "hotspot", "hotspot_fraction": 0.1, "hotspot_probability": 0.8})
    )
    spec = _spec("      kind: hotspot\n      hotspot_fraction: 0.1\n      hotspot_probability: 0.9")
    estimate = estimate_query_latency_us(spec, spec.queries[0], "robin_hood_hash", profile=profile)
    assert estimate.source.startswith("BOOTSTRAP_PRIOR_DISTRIBUTION_UNMODELED:hotspot")
    assert estimate.uncertainty_ratio == 0.80


def test_zipf_theta_is_part_of_measurement_identity() -> None:
    profile = profile_from_smoke_payload(_payload({"kind": "zipf", "zipf_theta": 0.99}))
    matching = _spec("      kind: zipf\n      zipf_theta: 0.99")
    mismatched = _spec("      kind: zipf\n      zipf_theta: 1.2")
    assert estimate_query_latency_us(
        matching, matching.queries[0], "robin_hood_hash", profile=profile
    ).source.startswith("CALIBRATED:")
    assert estimate_query_latency_us(
        mismatched, mismatched.queries[0], "robin_hood_hash", profile=profile
    ).source.startswith("BOOTSTRAP_PRIOR_DISTRIBUTION_UNMODELED:zipf")


def test_distribution_protocol_is_preserved_in_import_provenance() -> None:
    profile = profile_from_smoke_payload(_payload({"kind": "uniform"}))
    assert profile.schema_version == 4
    assert profile.protocol == "morpheus-distribution-calibration-v1"
    assert profile.machine["distribution_protocol"] == "morpheus-access-distribution-v1"
    assert profile.measurements[0].access_distribution is not None
    assert profile.measurements[0].access_distribution.kind.value == "uniform"


def test_build_measurement_cannot_claim_access_distribution() -> None:
    with pytest.raises(ValueError, match="build calibration must not claim an access distribution"):
        CalibrationMeasurement(
            primitive="robin_hood_hash",
            implementation_id="morpheus.RobinHoodHashIndex.v1",
            operation="build",
            access_distribution={"kind": "uniform"},
            ns_per_op=20.0,
        )
