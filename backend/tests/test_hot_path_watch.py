from __future__ import annotations

from fastapi.testclient import TestClient

from app.server import app


client = TestClient(app)


SPEC = """version: mws-0.1
name: hot_path_watch_test
record_count: 20000
fields:
  - name: id
    type: uint64
    cardinality: 20000
queries:
  - kind: point_lookup
    field: id
    weight: 1.0
constraints:
  memory_mb: 64
  update_rate: 50
objective:
  latency: 1.0
  memory: 0.15
  update: 0.1
  build: 0.05
"""


def _watch(baseline: list[int], observed: list[int]):
    return client.post(
        "/api/v2/doctor/hot-path/watch",
        json={
            "spec_text": SPEC,
            "current_structure": "std_unordered_map",
            "query_index": 0,
            "baseline_keys": baseline,
            "observed_keys": observed,
            "threshold": 0.20,
            "strategy": "auto",
        },
    )


def test_hot_path_watch_keeps_stable_finite_window_without_control_authority() -> None:
    window = [1, 2, 3, 4, 5, 6, 7, 8] * 25
    response = _watch(window, list(window))

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "morpheus-hot-path-watch-v1"
    assert payload["drift"]["drifted"] is False
    assert payload["decision"]["candidate_changed"] is False
    assert payload["decision"]["route_primitive_changed"] is False
    assert payload["decision"]["action"] == "KEEP_AND_MONITOR"
    assert payload["decision"]["severity"] == "LOW"
    assert payload["eligible_for_runtime_automatic_control"] is False
    assert "target-machine measurement" in payload["truth_boundary"]


def test_hot_path_watch_surfaces_material_trace_change_and_next_gate() -> None:
    baseline = list(range(200))
    observed = [7] * 180 + list(range(20))
    response = _watch(baseline, observed)

    assert response.status_code == 200
    payload = response.json()
    assert payload["drift"]["drifted"] is True
    assert payload["baseline"]["analysis"]["suggested_distribution"] == "sequential"
    assert payload["observed"]["analysis"]["suggested_distribution"] == "hotspot"
    assert "kind: hotspot" in payload["observed"]["draft_spec_text"]
    assert payload["decision"]["distribution_label_changed"] is True
    assert payload["decision"]["action"] in {
        "REMEASURE_RECOMMENDATION_AFTER_DRIFT",
        "RESYNTHESIZE_MEASURE_VERIFY_SHADOW",
    }
    if payload["decision"]["action"] == "RESYNTHESIZE_MEASURE_VERIFY_SHADOW":
        assert (
            payload["decision"]["candidate_changed"]
            or payload["decision"]["route_primitive_changed"]
        )
        assert payload["decision"]["severity"] == "HIGH"
    else:
        assert payload["decision"]["candidate_changed"] is False
        assert payload["decision"]["route_primitive_changed"] is False
        assert payload["decision"]["severity"] == "MEDIUM"
    assert payload["decision"]["recommended_next_gate"]
    assert payload["eligible_for_runtime_automatic_control"] is False


def test_hot_path_watch_rejects_query_index_outside_current_workload() -> None:
    response = client.post(
        "/api/v2/doctor/hot-path/watch",
        json={
            "spec_text": SPEC,
            "current_structure": "std_unordered_map",
            "query_index": 3,
            "baseline_keys": [1, 2, 3, 4],
            "observed_keys": [1, 2, 3, 4],
        },
    )

    assert response.status_code == 422
    assert "outside the workload query range" in response.json()["detail"]


def test_hot_path_watch_does_not_persist_or_apply_observed_draft_implicitly() -> None:
    response = _watch([0, 1, 2, 3] * 25, [9] * 80 + list(range(20)))

    assert response.status_code == 200
    payload = response.json()
    assert payload["observed"]["draft_spec_text"] != SPEC
    assert payload["source_spec_hash"] != payload["observed"]["draft_spec_hash"]
    assert payload["evidence_state"] == "FINITE_TRACE_DRIFT_REEVALUATED_MODEL_RECOMMENDATION_NOT_CONTROL_EVIDENCE"
    assert "explicit user review" in payload["truth_boundary"]
