from __future__ import annotations

from fastapi.testclient import TestClient

from app.server import app


client = TestClient(app)


def test_feature_registry_api_is_versioned_and_fail_closed() -> None:
    response = client.get("/api/v2/system/features")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "morpheus-feature-registry-v1"
    by_id = {item["id"]: item for item in payload["features"]}
    assert by_id["trace_distribution_classifier"]["maturity"] == "research"
    assert by_id["trace_distribution_classifier"]["automatic_control_allowed"] is False
    assert by_id["native_cross_process_hot_swap"]["maturity"] == "blocked"

    blocked = client.post(
        "/api/v2/system/features/evaluate",
        json={"features": ["trace_distribution_classifier"], "automatic_control": True},
    )
    assert blocked.status_code == 200
    assert blocked.json()["decision"] == "DENY_FAIL_CLOSED"


def test_feature_activation_api_rejects_unknown_feature() -> None:
    response = client.post(
        "/api/v2/system/features/evaluate",
        json={"features": ["not-a-real-feature"], "automatic_control": False},
    )
    assert response.status_code == 422
    assert "unknown features" in response.json()["detail"]


def test_schema_contract_fingerprint_is_deterministic_and_contains_critical_routes() -> None:
    first = client.get("/api/v2/system/schema-contract")
    second = client.get("/api/v2/system/schema-contract")
    assert first.status_code == 200
    assert second.status_code == 200
    first_payload = first.json()
    second_payload = second.json()
    assert first_payload["schema"] == "morpheus-api-contract-fingerprint-v1"
    assert len(first_payload["sha256"]) == 64
    assert first_payload["sha256"] == second_payload["sha256"]
    paths = first_payload["contract"]["paths"]
    required = {
        "/api/health",
        "/api/synthesize",
        "/api/v2/capabilities",
        "/api/v2/completion",
        "/api/v2/system/features",
        "/api/v2/system/features/evaluate",
        "/api/v2/system/schema-contract",
    }
    assert required <= set(paths)


def test_openapi_operation_ids_are_unique() -> None:
    schema = app.openapi()
    operation_ids: list[str] = []
    for operations in schema.get("paths", {}).values():
        for method, operation in operations.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            operation_id = operation.get("operationId")
            assert operation_id
            operation_ids.append(operation_id)
    assert len(operation_ids) == len(set(operation_ids))
