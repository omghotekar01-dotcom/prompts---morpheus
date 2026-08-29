from __future__ import annotations

from fastapi.testclient import TestClient

from app.access_trace_phases import analyze_trace_phases
from app.server import app


client = TestClient(app)


def test_stable_repeated_windows_do_not_create_phase_boundaries() -> None:
    window = [0, 1, 2, 3, 4, 5, 6, 7] * 25
    report = analyze_trace_phases(window * 3, window_size=len(window), drift_threshold=0.2)
    assert len(report.windows) == 3
    assert report.boundaries == ()
    labels = {item.suggested_distribution for item in report.windows}
    assert len(labels) == 1
    assert report.as_dict()["eligible_for_runtime_automatic_control"] is False


def test_abrupt_hot_key_change_creates_phase_boundary() -> None:
    first = [0] * 180 + list(range(1, 21))
    second = [100] * 180 + list(range(101, 121))
    report = analyze_trace_phases(first + second, window_size=200, step_size=200, drift_threshold=0.2)
    assert len(report.windows) == 2
    assert len(report.boundaries) == 1
    boundary = report.boundaries[0]
    assert boundary.boundary_sample_index == 200
    assert boundary.key_frequency_tv_distance > 0.9
    assert boundary.top_10_percent_key_jaccard == 0.0


def test_overlapping_windows_report_candidate_boundaries_not_calibrated_change_points() -> None:
    trace = list(range(200)) + [7] * 200 + list(range(200, 400))
    report = analyze_trace_phases(trace, window_size=100, step_size=50, drift_threshold=0.25)
    payload = report.as_dict()
    assert payload["window_count"] > 2
    assert payload["boundary_count"] >= 1
    assert payload["evidence_state"] == "ROLLING_FINITE_TRACE_PHASE_CANDIDATES_NOT_AUTOMATIC_CONTROL_EVIDENCE"
    assert "not a statistically calibrated online detector" in payload["truth_boundary"]


def test_phase_analysis_research_api_is_bounded_and_truthful() -> None:
    response = client.post(
        "/api/v2/research/access-trace/phases",
        json={
            "keys": ([0] * 50 + list(range(1, 51))) + ([100] * 50 + list(range(101, 151))),
            "window_size": 100,
            "step_size": 100,
            "drift_threshold": 0.2,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["boundary_count"] == 1
    assert payload["eligible_for_runtime_automatic_control"] is False
    assert payload["boundaries"][0]["boundary_sample_index"] == 100
