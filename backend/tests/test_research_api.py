from __future__ import annotations

import textwrap

from fastapi.testclient import TestClient

from app.main import app


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
    assert payload["report"]["evidence_state"] == "SEARCH_HEURISTIC_EVALUATED_AGAINST_EXHAUSTIVE_MODEL_ORACLE"
