from __future__ import annotations

from fastapi.testclient import TestClient

from app.dataplane import DATA_PLANE
from app.server import app


client = TestClient(app)


def test_v2_capabilities_and_engineering_completion_are_consistent() -> None:
    capabilities = client.get("/api/v2/capabilities")
    assert capabilities.status_code == 200
    payload = capabilities.json()
    assert payload["bplus_tree_primitive"] == "IMPLEMENTED_TESTED"
    assert payload["paired_baseline_matrix"].startswith("IMPLEMENTED")
    assert payload["local_dataplane_swap"] == "IMPLEMENTED_TESTED_IN_PROCESS"
    assert payload["runtime_hot_swap"] == "NOT_IMPLEMENTED_NATIVE_CROSS_PROCESS"

    completion = client.get("/api/v2/completion")
    assert completion.status_code == 200
    report = completion.json()
    assert report["engineering_percent"] == 100.0
    assert report["passed_gates"] == report["total_gates"]
    assert "publication acceptance" in report["excluded_outcomes"]


def test_v2_dataplane_bootstrap_and_read_surface() -> None:
    DATA_PLANE.reset()
    artifact = "a" * 64
    response = client.post(
        "/api/v2/dataplane/deployments",
        json={
            "deployment_id": "api-deployment",
            "candidate_id": "candidate-a",
            "artifact_sha256": artifact,
            "metadata": {"test": True},
        },
    )
    assert response.status_code == 200
    assert response.json()["active"]["candidate_id"] == "candidate-a"

    detail = client.get("/api/v2/dataplane/deployments/api-deployment")
    assert detail.status_code == 200
    assert detail.json()["active"]["artifact_sha256"] == artifact
    assert detail.json()["truth_boundary"].startswith("Atomic local routing")
    DATA_PLANE.reset()
