from __future__ import annotations

import textwrap

from fastapi.testclient import TestClient

from app.calibration import CALIBRATIONS
from app.catalog import PRIMITIVES
from app.models import CalibrationMeasurement, CalibrationProfile
from app.server import app


SPEC = textwrap.dedent(
    """
    version: mws-0.1
    name: research_api_search
    record_count: 10000
    fields:
      - name: id
        type: uint64
        cardinality: 10000
      - name: age
        type: uint32
        cardinality: 100
    queries:
      - kind: point_lookup
        field: id
        weight: 0.6
      - kind: range_scan
        field: age
        weight: 0.4
        selectivity: 0.05
    constraints:
      memory_mb: 64
    """
).strip()

MULTI_ROUTE_SPEC = textwrap.dedent(
    """
    version: mws-0.1
    name: research_api_multi_route
    record_count: 10000
    fields:
      - name: id
        type: uint64
        cardinality: 10000
    queries:
      - kind: point_lookup
        field: id
        weight: 0.25
      - kind: point_lookup
        field: id
        weight: 0.25
      - kind: point_lookup
        field: id
        weight: 0.25
      - kind: point_lookup
        field: id
        weight: 0.25
    constraints:
      memory_mb: 64
    """
).strip()


def test_prediction_evaluation_api_preserves_measurement_truth_boundary() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/research/predictions/evaluate",
        json={
            "metric": "latency_us",
            "points": [
                {"label": "a", "predicted": 1.0, "measured": 1.2},
                {"label": "b", "predicted": 2.0, "measured": 2.5},
                {"label": "c", "predicted": 3.0, "measured": 2.8},
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["metric"] == "latency_us"
    assert payload["evaluation"]["sample_count"] == 3
    assert payload["evaluation"]["evidence_state"] == "EVALUATED_AGAINST_CALLER_SUPPLIED_MEASUREMENTS"
    assert "does not establish how they were collected" in payload["truth_note"]


def test_search_quality_api_compares_beam_with_bounded_model_oracle() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/research/search/compare",
        json={"spec_text": SPEC, "beam_width": 2, "exhaustive_limit": 1000},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["report"]["exhaustive_evaluated"] > 0
    assert payload["report"]["beam_evaluated"] <= 2
    assert payload["report"]["heuristic_strategy"] == "beam"
    assert payload["report"]["evidence_state"] == "SEARCH_HEURISTIC_EVALUATED_AGAINST_EXHAUSTIVE_MODEL_ORACLE"


def test_v2_decision_confidence_endpoint_uses_active_measurement_truth_boundary() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v2/research/decision-confidence",
        json={"spec_text": MULTI_ROUTE_SPEC, "strategy": "exhaustive", "interval_scale": 1.0},
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["spec_hash"]) == 64
    assert payload["assessment"]["action"] in {"ACCEPT_MODELED_WINNER", "BENCHMARK_MORE"}
    assert payload["evidence_state"] == "MODEL_UNCERTAINTY_HEURISTIC_NOT_EMPIRICAL_CONFIDENCE"
    assert "not calibrated statistical confidence intervals" in payload["assessment"]["truth_boundary"]


def test_v2_compare_all_reports_greedy_and_beam_against_same_model_oracle() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v2/research/search/compare-all",
        json={"spec_text": MULTI_ROUTE_SPEC, "beam_width": 8, "exhaustive_limit": 10000},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["greedy"]["heuristic_strategy"] == "greedy"
    assert payload["beam"]["heuristic_strategy"] == "beam"
    assert payload["greedy"]["exhaustive_evaluated"] == payload["beam"]["exhaustive_evaluated"]
    assert payload["greedy"]["heuristic_evaluated"] == 1
    assert payload["beam"]["heuristic_evaluated"] <= 8
    assert "not empirical hardware regret" in payload["truth_boundary"]


def test_v2_calibration_coverage_endpoint_audits_implementation_identity() -> None:
    profile_id = "research-api-coverage"
    implementation_id = PRIMITIVES["robin_hood_hash"].implementation_id
    profile = CalibrationProfile(
        id=profile_id,
        schema_version=3,
        evidence_state="MEASURED_LOCAL_PROCESS_REPEATED_IMPLEMENTATION_BOUND",
        protocol="morpheus-calibration-v3",
        record_count=1000,
        operations=1000,
        measurements=[
            CalibrationMeasurement(
                primitive="robin_hood_hash",
                implementation_id=implementation_id,
                operation="point_lookup",
                ns_per_op=25.0,
            )
        ],
    )
    CALIBRATIONS.register(profile, persist=False)
    client = TestClient(app)
    response = client.get(f"/api/v2/research/calibration/coverage/{profile_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["profile_id"] == profile_id
    assert payload["matched_cells"] == 1
    assert payload["required_cells"] > payload["matched_cells"]
    assert payload["evidence_state"] == "CALIBRATION_COVERAGE_AUDITED_NOT_PERFORMANCE_EVIDENCE"
    assert "does not establish" in payload["truth_boundary"]
