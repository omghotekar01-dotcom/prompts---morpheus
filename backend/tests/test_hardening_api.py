from __future__ import annotations

from fastapi.testclient import TestClient

from app.calibration import CALIBRATIONS
from app.catalog import PRIMITIVES
from app.models import (
    AccessDistribution,
    CalibrationMeasurement,
    CalibrationProfile,
    QueryDistributionSpec,
)
from app.server import app


client = TestClient(app)


def test_feature_registry_api_is_versioned_fingerprinted_and_fail_closed() -> None:
    first = client.get("/api/v2/system/features")
    second = client.get("/api/v2/system/features")
    assert first.status_code == 200
    assert second.status_code == 200
    payload = first.json()
    assert payload["schema"] == "morpheus-feature-registry-v1"
    assert len(payload["sha256"]) == 64
    assert payload["sha256"] == second.json()["sha256"]
    assert all(ch in "0123456789abcdef" for ch in payload["sha256"])
    assert "not a signature" in payload["truth_boundary"].lower()

    by_id = {item["id"]: item for item in payload["features"]}
    assert by_id["trace_distribution_classifier"]["maturity"] == "research"
    assert by_id["trace_distribution_classifier"]["automatic_control_allowed"] is False
    assert by_id["native_cross_process_hot_swap"]["maturity"] == "blocked"

    blocked = client.post(
        "/api/v2/system/features/evaluate",
        json={"features": ["trace_distribution_classifier"], "automatic_control": True},
    )
    assert blocked.status_code == 200
    assert blocked.json()["decision"] == "DENY_FAIL_CLOSED"


def test_feature_activation_api_rejects_unknown_feature() -> None:
    response = client.post(
        "/api/v2/system/features/evaluate",
        json={"features": ["not-a-real-feature"], "automatic_control": False},
    )
    assert response.status_code == 422
    assert "unknown features" in response.json()["detail"]


def test_workload_calibration_coverage_api_is_read_only_and_fail_closed() -> None:
    implementation_id = PRIMITIVES["robin_hood_hash"].implementation_id
    profile = CalibrationProfile(
        id="hardening-api-distribution-profile",
        schema_version=4,
        evidence_state="MEASURED_LOCAL_PROCESS_REPEATED_IMPLEMENTATION_DISTRIBUTION_BOUND",
        protocol="morpheus-distribution-calibration-v1",
        record_count=1000,
        operations=5000,
        seed=1337,
        machine={"cpu": "test"},
        measurements=[
            CalibrationMeasurement(
                primitive="robin_hood_hash",
                implementation_id=implementation_id,
                operation="point_lookup",
                access_distribution=QueryDistributionSpec(
                    kind=AccessDistribution.HOTSPOT,
                    hotspot_fraction=0.1,
                    hotspot_probability=0.8,
                ),
                ns_per_op=40.0,
                repetitions=5,
            )
        ],
    )
    CALIBRATIONS.register(profile, persist=False)
    CALIBRATIONS.deactivate(persist=False)
    spec_text = """
version: mws-0.1
name: coverage_api
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
""".strip()

    response = client.post(
        "/api/v2/system/calibration/coverage/workload",
        json={
            "profile_id": profile.id,
            "spec_text": spec_text,
            "primitive_names": ["robin_hood_hash"],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["profile_id"] == profile.id
    assert payload["scale_matches_profile"] is True
    assert payload["matched_cells"] == 1
    assert payload["coverage_ratio"] == 1.0
    assert payload["cells"][0]["status"] == "MATCHED"
    assert CALIBRATIONS.active_profile_id is None

    missing = client.post(
        "/api/v2/system/calibration/coverage/workload",
        json={"profile_id": "missing-profile", "spec_text": spec_text},
    )
    assert missing.status_code == 404

    bad_primitive = client.post(
        "/api/v2/system/calibration/coverage/workload",
        json={
            "profile_id": profile.id,
            "spec_text": spec_text,
            "primitive_names": ["not-a-primitive"],
        },
    )
    assert bad_primitive.status_code == 422


def test_schema_contract_fingerprint_is_deterministic_and_contains_critical_routes() -> None:
    first = client.get("/api/v2/system/schema-contract")
    second = client.get("/api/v2/system/schema-contract")
    assert first.status_code == 200
    assert second.status_code == 200
    first_payload = first.json()
    second_payload = second.json()
    assert first_payload["schema"] == "morpheus-api-contract-fingerprint-v1"
    assert len(first_payload["sha256"]) == 64
    assert first_payload["sha256"] == second_payload["sha256"]
    paths = first_payload["contract"]["paths"]
    required = {
        "/api/health",
        "/api/synthesize",
        "/api/v2/capabilities",
        "/api/v2/completion",
        "/api/v2/migration/generated/bundle",
        "/api/v2/system/features",
        "/api/v2/system/features/evaluate",
        "/api/v2/system/calibration/coverage/workload",
        "/api/v2/system/schema-contract",
    }
    assert required <= set(paths)


def test_openapi_operation_ids_are_unique() -> None:
    schema = app.openapi()
    operation_ids: list[str] = []
    for operations in schema.get("paths", {}).values():
        for method, operation in operations.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            operation_id = operation.get("operationId")
            assert operation_id
            operation_ids.append(operation_id)
    assert len(operation_ids) == len(set(operation_ids))
