from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.operational_metrics import (
    OperationalMetrics,
    RequestObservabilityMiddleware,
    canonical_request_id,
    normalize_metric_path,
)


def test_metric_path_normalization_removes_high_cardinality_identifiers() -> None:
    sha = "a" * 64
    assert normalize_metric_path(f"/api/artifacts/{sha}") == "/api/artifacts/:sha256"
    assert normalize_metric_path("/api/runs/123456") == "/api/runs/:int"
    assert normalize_metric_path("/api/jobs/123e4567-e89b-12d3-a456-426614174000") == "/api/jobs/:uuid"
    assert normalize_metric_path("/api/" + "x" * 100) == "/api/:opaque"


def test_request_id_accepts_canonical_client_value_and_replaces_invalid_input() -> None:
    assert canonical_request_id("pilot-request:42") == "pilot-request:42"
    generated = canonical_request_id("bad request id with spaces")
    assert len(generated) == 32
    assert generated.isalnum()


def test_observability_middleware_returns_correlation_header_and_sanitized_metrics() -> None:
    metrics = OperationalMetrics(max_route_keys=8)
    app = FastAPI()
    app.add_middleware(RequestObservabilityMiddleware, metrics=metrics)

    @app.get("/api/artifacts/{sha256}")
    def artifact(sha256: str) -> dict[str, str]:
        return {"sha256": sha256}

    client = TestClient(app)
    sha = "b" * 64
    response = client.get(
        f"/api/artifacts/{sha}?token=never-record-this",
        headers={"X-Morpheus-Request-ID": "pilot-req-1", "X-Morpheus-Key": "never-record-this-key"},
    )
    assert response.status_code == 200
    assert response.headers["x-morpheus-request-id"] == "pilot-req-1"
    assert response.headers["server-timing"].startswith("morpheus;dur=")

    snapshot = metrics.snapshot()
    assert snapshot["requests_total"] == 1
    assert snapshot["in_flight"] == 0
    assert snapshot["status_classes"]["2xx"] == 1
    assert snapshot["routes"][0]["path"] == "/api/artifacts/:sha256"
    serialized = str(snapshot)
    assert "never-record-this" not in serialized
    assert sha not in serialized


def test_route_cardinality_limit_is_a_hard_bound_with_overflow_bucket() -> None:
    metrics = OperationalMetrics(max_route_keys=3)
    for index in range(10):
        metrics.begin()
        metrics.finish(method="GET", path=f"/api/static-{index}", status_code=200, duration_ms=float(index))

    snapshot = metrics.snapshot()
    assert snapshot["route_key_count"] <= snapshot["route_key_limit"] == 3
    assert snapshot["overflow_route_observations"] > 0
    assert any(item["path"] == "/:other" for item in snapshot["routes"])


def test_4xx_and_5xx_are_aggregated_without_request_payloads() -> None:
    metrics = OperationalMetrics(max_route_keys=4)
    metrics.begin()
    metrics.finish(method="POST", path="/api/synthesize", status_code=422, duration_ms=4.0)
    metrics.begin()
    metrics.finish(method="POST", path="/api/synthesize", status_code=500, duration_ms=7.0)

    snapshot = metrics.snapshot()
    assert snapshot["status_classes"]["4xx"] == 1
    assert snapshot["status_classes"]["5xx"] == 1
    route = snapshot["routes"][0]
    assert route["requests"] == 2
    assert route["errors_4xx"] == 1
    assert route["errors_5xx"] == 1
