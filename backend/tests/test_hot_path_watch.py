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
    assert payload["freshness_passport"]["freshness_state"] == "CURRENT_FOR_SUPPLIED_WINDOWS"
    assert payload["freshness_passport"]["rollout_disposition"] == "NO_CHANGE_REQUIRED_CONTINUE_MONITORING"
    assert len(payload["freshness_passport"]["passport_sha256"]) == 64
    assert payload["freshness_passport"]["eligible_for_runtime_automatic_control"] is False
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
    passport = payload["freshness_passport"]
    assert passport["freshness_state"] in {
        "REVIEW_REQUIRED_AFTER_DRIFT",
        "SUPERSEDED_FOR_SUPPLIED_WINDOWS",
    }
    assert "FRESH_TRACE_REVALIDATION_BEFORE_CUTOVER" in passport["change_ticket"]["required_evidence_gates"]
    assert passport["change_ticket"]["automatic_cutover_allowed"] is False
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
    passport = payload["freshness_passport"]
    assert passport["evidence_binding"]["source_spec_hash"] == payload["source_spec_hash"]
    assert passport["evidence_binding"]["observed_draft_spec_hash"] == payload["observed"]["draft_spec_hash"]
    assert "explicit user review" in payload["truth_boundary"]


def test_hot_path_trace_intake_normalizes_csv_without_persisting_raw_content() -> None:
    response = client.post(
        "/api/v2/doctor/hot-path/trace-intake",
        json={
            "content": "timestamp,sku_hash,op\n1,101,read\n2,101,read\n3,202,read\n",
            "format_hint": "csv",
            "key_field": "sku_hash",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "morpheus-real-workload-trace-intake-v1"
    assert payload["keys"] == [101, 101, 202]
    assert payload["sample_count"] == 3
    assert payload["selected_key_field"] == "sku_hash"
    assert len(payload["input_sha256"]) == 64
    assert len(payload["normalized_window_sha256"]) == 64
    assert payload["eligible_for_runtime_automatic_control"] is False


def test_hot_path_trace_intake_fails_closed_on_ambiguous_json_columns() -> None:
    response = client.post(
        "/api/v2/doctor/hot-path/trace-intake",
        json={
            "content": '[{"key":1,"id":10},{"key":2,"id":11}]',
            "format_hint": "json",
        },
    )

    assert response.status_code == 422
    assert "multiple possible key fields" in response.json()["detail"]


def test_hot_path_trace_intake_requires_explicit_opt_in_before_dropping_bad_rows() -> None:
    strict = client.post(
        "/api/v2/doctor/hot-path/trace-intake",
        json={
            "content": "key\n1\nbroken\n2\n",
            "format_hint": "csv",
        },
    )
    permissive = client.post(
        "/api/v2/doctor/hot-path/trace-intake",
        json={
            "content": "key\n1\nbroken\n2\n",
            "format_hint": "csv",
            "allow_invalid_rows": True,
        },
    )

    assert strict.status_code == 422
    assert permissive.status_code == 200
    payload = permissive.json()
    assert payload["keys"] == [1, 2]
    assert payload["rejected_count"] == 1
    assert "explicitly" in payload["truth_boundary"]
