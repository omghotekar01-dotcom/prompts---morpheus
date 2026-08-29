from __future__ import annotations

from fastapi.testclient import TestClient

from app.access_trace_drift import compare_access_trace_windows
from app.server import app


client = TestClient(app)


def test_identical_empirical_windows_have_zero_frequency_drift() -> None:
    baseline = [1, 2, 3, 1, 2, 3] * 20
    report = compare_access_trace_windows(baseline, list(baseline), threshold=0.2)
    assert report.key_frequency_tv_distance == 0.0
    assert report.normalized_jensen_shannon_divergence == 0.0
    assert report.top_10_percent_key_jaccard == 1.0
    assert not report.drifted


def test_disjoint_key_windows_reach_maximum_frequency_drift() -> None:
    baseline = [1, 2, 3, 4] * 25
    observed = [101, 102, 103, 104] * 25
    report = compare_access_trace_windows(baseline, observed, threshold=0.2)
    assert report.key_frequency_tv_distance == 1.0
    assert report.normalized_jensen_shannon_divergence == 1.0
    assert report.top_10_percent_key_jaccard == 0.0
    assert report.drifted
    assert report.as_dict()["eligible_for_runtime_automatic_control"] is False


def test_hot_key_shift_is_visible_even_with_overlapping_key_domain() -> None:
    baseline = [0] * 80 + list(range(1, 21))
    observed = [20] * 80 + list(range(0, 20))
    report = compare_access_trace_windows(baseline, observed, threshold=0.2)
    assert report.key_frequency_tv_distance > 0.7
    assert report.top_10_percent_key_jaccard < 1.0
    assert report.drifted


def test_access_trace_compare_api_preserves_non_control_truth_boundary() -> None:
    response = client.post(
        "/api/v2/research/access-trace/compare",
        json={
            "baseline_keys": [1, 1, 1, 2, 3, 4],
            "observed_keys": [9, 9, 9, 8, 7, 6],
            "threshold": 0.2,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["drifted"] is True
    assert payload["eligible_for_runtime_automatic_control"] is False
    assert "finite empirical key-frequency windows" in payload["truth_boundary"]
