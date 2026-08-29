from __future__ import annotations

from fastapi.testclient import TestClient

from app.server import app


client = TestClient(app)


def test_runtime_api_detects_distribution_shift_with_stable_operation_mix() -> None:
    session_id = "api-distribution-drift"
    start = client.post(
        "/api/runtime/sessions",
        json={
            "session_id": session_id,
            "active_candidate_id": "candidate-uniform",
            "drift_threshold": 0.2,
            "cooldown_windows": 0,
            "baseline": {
                "operation_mix": {"point_lookup": 1.0},
                "access_distribution_mix": {"uniform": 1.0},
                "expected_future_queries": 100000,
                "sequence": 0,
            },
        },
    )
    assert start.status_code == 200
    assert start.json()["baseline_access_distribution_mix"] == {"uniform": 1.0}

    observed = client.post(
        f"/api/runtime/sessions/{session_id}/observe",
        json={
            "snapshot": {
                "operation_mix": {"point_lookup": 1.0},
                "access_distribution_mix": {"hotspot": 1.0},
                "expected_future_queries": 100000,
                "sequence": 1,
            },
            "alternative_candidate_id": "candidate-hotspot",
            "current_predicted_latency_us": 10.0,
            "alternative_predicted_latency_us": 4.0,
            "estimated_switching_cost_us": 1000.0,
        },
    )
    assert observed.status_code == 200
    payload = observed.json()
    drift = payload["decision"]["drift"]
    assert drift["operation_distance"] == 0.0
    assert drift["access_distribution_distance"] == 1.0
    assert drift["method"] == "max_component_tv"
    assert drift["drifted"] is True
    assert payload["decision"]["action"] == "SWITCH_RECOMMENDED"
    assert payload["decision"]["evidence_state"] == "PREDICTED_NOT_MEASURED_RUNTIME_CONTROL"
    assert payload["session"]["pending_candidate_id"] == "candidate-hotspot"
