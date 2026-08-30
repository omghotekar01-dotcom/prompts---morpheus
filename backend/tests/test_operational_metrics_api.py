from __future__ import annotations

from fastapi.testclient import TestClient

from app.server import app


client = TestClient(app)


def test_canonical_server_emits_request_id_and_operational_metrics() -> None:
    health = client.get("/api/health", headers={"X-Morpheus-Request-ID": "integration-health-1"})
    assert health.status_code == 200
    assert health.headers["x-morpheus-request-id"] == "integration-health-1"
    assert health.headers["server-timing"].startswith("morpheus;dur=")

    response = client.get("/api/v2/system/operational-metrics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "morpheus-operational-metrics-v1"
    assert payload["evidence_state"] == "PROCESS_LOCAL_OPERATIONAL_TELEMETRY"
    assert payload["requests_total"] >= 1
    assert payload["route_key_count"] <= payload["route_key_limit"]
    assert any(item["path"] == "/api/health" for item in payload["routes"])
    assert any("not an HA telemetry backend" in item for item in payload["truth_boundaries"])
