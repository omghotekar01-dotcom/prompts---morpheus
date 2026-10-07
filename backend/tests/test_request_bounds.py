from fastapi.testclient import TestClient

from app.server import app


client = TestClient(app)


def test_core_spec_endpoints_reject_oversized_workload_text() -> None:
    oversized = "x" * 256_001

    response = client.post("/api/validate", json={"spec_text": oversized})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(
        item.get("loc") == ["body", "spec_text"]
        and item.get("type") == "string_too_long"
        for item in detail
    )
