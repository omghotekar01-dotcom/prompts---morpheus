from __future__ import annotations

from fastapi.testclient import TestClient

from app.feature_registry import evaluate_feature_activation, registry_payload
from app.server import app


client = TestClient(app)


MIXED_SPEC = """version: mws-0.1
name: api_hot_path
record_count: 20000
fields:
  - name: id
    type: uint64
    cardinality: 20000
  - name: created_at
    type: uint64
    cardinality: 20000
queries:
  - kind: point_lookup
    field: id
    weight: 0.7
    distribution:
      kind: hotspot
      hotspot_fraction: 0.05
      hotspot_probability: 0.9
  - kind: range_scan
    field: created_at
    weight: 0.3
    selectivity: 0.02
constraints:
  memory_mb: 64
  update_rate: 200
objective:
  latency: 1.0
  memory: 0.15
  update: 0.1
  build: 0.05
"""


def test_hot_path_options_expose_common_current_structures_without_control_authority() -> None:
    response = client.get("/api/v2/doctor/hot-path/options")
    assert response.status_code == 200
    payload = response.json()
    ids = {item["id"] for item in payload["current_structures"]}
    assert {"std_unordered_map", "std_map", "sorted_vector", "linear_scan", "custom_or_unknown"} <= ids
    assert payload["automatic_control_allowed"] is False
    assert "in-memory data structures" in payload["problem"]


def test_hot_path_doctor_quantifies_semantic_gap_without_fabricating_speedup() -> None:
    response = client.post(
        "/api/v2/doctor/hot-path",
        json={
            "spec_text": MIXED_SPEC,
            "current_structure": "std_unordered_map",
            "strategy": "auto",
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["schema"] == "morpheus-hot-path-doctor-v1"
    assert payload["problem"]["category"] == "APPLICATION_HOT_PATH_DATA_STRUCTURE_SELECTION"
    assert payload["current_structure"]["supported_weight_ratio"] == 0.7
    assert payload["current_structure"]["unsupported_weight_ratio"] == 0.3
    assert payload["current_structure"]["unsupported_operations"] == ["range_scan"]
    assert payload["recommendation"]["candidate_id"]
    assert payload["recommendation"]["routes"]
    assert payload["launch_state"] == "RECOMMENDATION_REQUIRES_LOCAL_MEASUREMENT_AND_VERIFICATION"
    assert payload["automatic_control_allowed"] is False
    assert payload["next_gate"].startswith("MEASURE_")
    assert "not a benchmark" in payload["truth_boundary"]
    assert "speedup" in payload["truth_boundary"]

    route_primitives = {route["primitive"] for route in payload["recommendation"]["routes"]}
    assert "robin_hood_hash" in route_primitives
    assert any(
        route["query_kind"] == "range_scan"
        and route["primitive"] in {"sorted_array", "ordered_tree"}
        for route in payload["recommendation"]["routes"]
    )

    gates = {step["gate"] for step in payload["migration_playbook"]}
    assert "LOCAL_MEASUREMENT_REQUIRED_BEFORE_PERFORMANCE_CLAIM" in gates
    assert "CORRECTNESS_BEFORE_CUTOVER" in gates
    assert "HUMAN_AUTHORIZED_DEPLOYMENT_ONLY" in gates


def test_hot_path_doctor_keeps_unknown_current_implementation_unknown() -> None:
    response = client.post(
        "/api/v2/doctor/hot-path",
        json={
            "spec_text": MIXED_SPEC,
            "current_structure": "custom_or_unknown",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    current = payload["current_structure"]
    assert current["supported_weight_ratio"] is None
    assert current["unsupported_weight_ratio"] is None
    assert current["evidence_state"] == "USER_DECLARED_CURRENT_STRUCTURE_NOT_BENCHMARKED"
    assert "cannot truthfully compare" in payload["problem"]["summary"]


def test_hot_path_doctor_rejects_unknown_structure_id() -> None:
    response = client.post(
        "/api/v2/doctor/hot-path",
        json={"spec_text": MIXED_SPEC, "current_structure": "magic_ai_map"},
    )
    assert response.status_code == 422
    assert "current_structure must be one of" in response.json()["detail"]


def test_hot_path_doctor_blocks_when_constraints_make_every_candidate_infeasible() -> None:
    impossible = """version: mws-0.1
name: impossible_memory
record_count: 100000
fields:
  - name: id
    type: uint64
    cardinality: 100000
queries:
  - kind: point_lookup
    field: id
    weight: 1.0
constraints:
  memory_mb: 0.001
objective:
  latency: 1.0
  memory: 1.0
"""
    response = client.post(
        "/api/v2/doctor/hot-path",
        json={"spec_text": impossible, "current_structure": "std_unordered_map"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["recommendation"] is None
    assert payload["launch_state"] == "BLOCKED_NO_FEASIBLE_CANDIDATE"
    assert payload["migration_playbook"][0]["gate"] == "NO_FEASIBLE_CANDIDATE"


def test_hot_path_doctor_is_registered_but_denied_for_automatic_control() -> None:
    features = registry_payload()["features"]
    doctor = next(item for item in features if item["id"] == "hot_path_doctor")
    assert doctor["maturity"] == "guarded"
    assert doctor["default_enabled"] is True
    assert doctor["automatic_control_allowed"] is False
    assert "generated_candidate_measurement" in doctor["dependencies"]

    decision = evaluate_feature_activation(["hot_path_doctor"], automatic_control=True)
    assert decision["allowed"] is False
    assert decision["decision"] == "DENY_FAIL_CLOSED"
    assert any(item["feature"] == "hot_path_doctor" for item in decision["blockers"])
