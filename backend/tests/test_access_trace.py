from __future__ import annotations

from fastapi.testclient import TestClient

from app.access_trace import analyze_access_trace
from app.models import AccessDistribution
from app.server import app


client = TestClient(app)


def test_access_trace_identifies_strong_sequential_window() -> None:
    report = analyze_access_trace(range(200))
    assert report.suggested_distribution == AccessDistribution.SEQUENTIAL
    assert report.sequential_adjacent_ratio == 1.0
    assert report.unique_ratio == 1.0
    assert report.evidence_state.endswith("NOT_CONTROL_EVIDENCE")
    assert report.as_dict()["eligible_for_runtime_automatic_control"] is False


def test_access_trace_identifies_concentrated_hotspot_window() -> None:
    keys = [0] * 900 + list(range(1, 101))
    report = analyze_access_trace(keys)
    assert report.suggested_distribution == AccessDistribution.HOTSPOT
    assert report.top_10_percent_key_mass >= 0.9
    assert report.normalized_frequency_entropy < 0.5


def test_access_trace_can_recognize_rank_frequency_zipf_shape_without_promoting_it() -> None:
    keys: list[int] = []
    for rank in range(1, 31):
        keys.extend([rank * 7] * max(1, int(1200 / (rank ** 1.1))))
    report = analyze_access_trace(keys)
    assert report.suggested_distribution == AccessDistribution.ZIPF
    assert report.zipf_theta_estimate is not None
    assert 0.9 <= report.zipf_theta_estimate <= 1.3
    assert report.zipf_log_rank_r2 is not None and report.zipf_log_rank_r2 >= 0.95
    assert report.as_dict()["eligible_for_runtime_automatic_control"] is False


def test_access_trace_uniform_fallback_is_explicitly_heuristic() -> None:
    pattern = [0, 5, 2, 8, 1, 7, 3, 9, 4, 6]
    report = analyze_access_trace(pattern * 20)
    assert report.suggested_distribution == AccessDistribution.UNIFORM
    assert report.top_10_percent_key_mass == 0.1
    assert report.normalized_frequency_entropy == 1.0
    assert "development heuristic" in report.suggestion_reason


def test_access_trace_research_endpoint_preserves_truth_boundary() -> None:
    response = client.post(
        "/api/v2/research/access-trace/analyze",
        json={"keys": [1, 2, 3, 4, 5, 6, 7, 8]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["suggested_distribution"] == "sequential"
    assert payload["eligible_for_runtime_automatic_control"] is False
    assert "not a goodness-of-fit test" in payload["truth_boundary"]
