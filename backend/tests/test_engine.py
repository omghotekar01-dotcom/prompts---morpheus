from __future__ import annotations

import json
import textwrap

from fastapi.testclient import TestClient

from app.engine import synthesize
from app.main import app
from app.models import SearchStrategy
from app.parser import parse_workload_text, semantic_hash


SAMPLE = textwrap.dedent(
    """
    version: mws-0.1
    name: users_demo
    record_count: 100000
    fields:
      - name: id
        type: uint64
        cardinality: 100000
      - name: age
        type: uint32
        cardinality: 90
      - name: city
        type: string
        cardinality: 400
    queries:
      - kind: point_lookup
        field: id
        weight: 0.55
      - kind: range_scan
        field: age
        weight: 0.25
        selectivity: 0.08
      - kind: filter
        field: city
        weight: 0.20
        selectivity: 0.03
    constraints:
      memory_mb: 64
      p99_latency_us: 250
      update_rate: 100
    """
).strip()


def test_parse_and_hash_are_deterministic() -> None:
    a = parse_workload_text(SAMPLE)
    b = parse_workload_text(SAMPLE)
    assert semantic_hash(a) == semantic_hash(b)
    assert a.name == "users_demo"


def test_synthesis_returns_feasible_composite_and_pareto_evidence() -> None:
    result = synthesize(parse_workload_text(SAMPLE))
    assert result.winner is not None
    assert result.winner.feasible
    assert "robin_hood_hash" in result.winner.unique_primitives
    assert "bitmap" in result.winner.unique_primitives
    assert result.evidence_state == "PREDICTED_NOT_MEASURED"
    assert result.generated_code is not None
    assert result.search_summary is not None
    assert result.search_summary.strategy == SearchStrategy.EXHAUSTIVE
    assert result.search_summary.evaluated_configurations == len(result.candidates)
    assert result.pareto_front
    assert all(candidate.feasible for candidate in result.pareto_front)


def test_auto_search_switches_to_deterministic_beam_under_budget() -> None:
    raw = json.dumps(
        {
            "version": "mws-0.1",
            "name": "beam_demo",
            "record_count": 10000,
            "fields": [{"name": "id", "type": "uint64", "cardinality": 10000}],
            "queries": [
                {"kind": "point_lookup", "field": "id", "weight": 1.0}
                for _ in range(8)
            ],
            "constraints": {"memory_mb": 64},
        }
    )
    spec = parse_workload_text(raw)
    result = synthesize(spec, max_candidates=32, beam_width=16)
    assert result.search_summary is not None
    assert result.search_summary.strategy == SearchStrategy.BEAM
    assert result.search_summary.truncated
    assert len(result.candidates) <= 16
    assert result.winner is not None


def test_greedy_search_is_one_path_deterministic_baseline() -> None:
    spec = parse_workload_text(SAMPLE)
    first = synthesize(spec, strategy=SearchStrategy.GREEDY)
    second = synthesize(spec, strategy=SearchStrategy.GREEDY)
    assert first.search_summary is not None
    assert first.search_summary.strategy == SearchStrategy.GREEDY
    assert first.search_summary.evaluated_configurations == 1
    assert first.search_summary.truncated
    assert first.winner is not None
    assert second.winner is not None
    assert first.winner.id == second.winner.id
    assert first.winner.model_dump(mode="json") == second.winner.model_dump(mode="json")
    assert any("greedy search followed one myopic prefix path" in warning for warning in first.warnings)


def test_greedy_strategy_is_available_through_synthesis_api() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/synthesize",
        json={"spec_text": SAMPLE, "strategy": "greedy", "max_candidates": 128, "beam_width": 16},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["search_summary"]["strategy"] == "greedy"
    assert payload["search_summary"]["evaluated_configurations"] == 1


def test_hard_memory_constraint_is_not_relaxed() -> None:
    impossible = SAMPLE.replace("memory_mb: 64", "memory_mb: 0.01")
    result = synthesize(parse_workload_text(impossible))
    assert result.winner is None
    assert result.candidates
    assert all(not candidate.feasible for candidate in result.candidates)


def test_unknown_field_is_rejected() -> None:
    bad = SAMPLE.replace("field: city", "field: missing")
    client = TestClient(app)
    response = client.post("/api/validate", json={"spec_text": bad})
    assert response.status_code == 422


def test_synthesis_api() -> None:
    client = TestClient(app)
    response = client.post("/api/synthesize", json={"spec_text": SAMPLE})
    assert response.status_code == 200
    payload = response.json()
    assert payload["winner"] is not None
    assert payload["evidence_state"] == "PREDICTED_NOT_MEASURED"
    assert payload["search_summary"]["strategy"] == "exhaustive"
    assert payload["pareto_front"]


def test_calibration_import_is_opt_in_and_changes_evidence_state_when_activated() -> None:
    client = TestClient(app)
    payload = {
        "profile_id": "lab-1",
        "schema_version": 3,
        "evidence_state": "MEASURED_LOCAL_PROCESS_REPEATED_IMPLEMENTATION_BOUND",
        "protocol": "morpheus-calibration-v3",
        "n": 100000,
        "operations": 50000,
        "seed": 1337,
        "machine": {"cpu": "ci-test"},
        "measurements": [
            {
                "primitive": "robin_hood_hash",
                "implementation_id": "morpheus.RobinHoodHashIndex.v1",
                "operation": "point_lookup",
                "ns_per_op": 35.0,
            },
            {
                "primitive": "robin_hood_hash",
                "implementation_id": "morpheus.RobinHoodHashIndex.v1",
                "operation": "build",
                "ns_per_op": 55.0,
            },
        ],
    }

    imported = client.post("/api/calibration/import", json={"payload": payload, "activate": False})
    assert imported.status_code == 200
    assert imported.json()["active"] is False

    before = client.post("/api/synthesize", json={"spec_text": SAMPLE}).json()
    assert before["evidence_state"] == "PREDICTED_NOT_MEASURED"

    activated = client.post("/api/calibration/activate/lab-1")
    assert activated.status_code == 200

    after = client.post("/api/synthesize", json={"spec_text": SAMPLE}).json()
    assert after["active_calibration_profile"] == "lab-1"
    assert after["evidence_state"] == "CALIBRATED_MODEL_NOT_END_TO_END_MEASURED"
    assert any("CALIBRATED" in candidate["prediction_source"] for candidate in after["candidates"])
    assert any("morpheus.RobinHoodHashIndex.v1" in candidate["prediction_source"] for candidate in after["candidates"])


def test_adaptation_decision_uses_transition_cost() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/adaptation/decide",
        json={
            "snapshot": {
                "operation_mix": {"range_scan": 0.8, "point_lookup": 0.2},
                "expected_future_queries": 100000,
                "observed_p99_latency_us": 20.0,
            },
            "current_predicted_latency_us": 10.0,
            "alternative_predicted_latency_us": 5.0,
            "estimated_switching_cost_us": 10000.0,
        },
    )
    assert response.status_code == 200
    assert response.json()["action"] == "SWITCH_RECOMMENDED"
