from __future__ import annotations

from fastapi.testclient import TestClient

from app.dataplane import DATA_PLANE
from app.server import app


client = TestClient(app)


def test_v2_capabilities_and_engineering_completion_are_consistent() -> None:
    capabilities = client.get("/api/v2/capabilities")
    assert capabilities.status_code == 200
    payload = capabilities.json()
    assert payload["mws"] == "IMPLEMENTED_TESTED"
    assert payload["workload_ir"] == "IMPLEMENTED_DETERMINISTIC_TYPED_HASHED"
    assert payload["greedy_search"] == "IMPLEMENTED_TESTED_MYOPIC_BASELINE"
    assert payload["heldout_grouped_ranking_evaluation"] == "IMPLEMENTED_TESTED_CALLER_MEASUREMENTS"
    assert payload["specialist_baseline_matrix"] == "IMPLEMENTED_OPTIONAL_ADAPTERS_CI_SMOKE"
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


def test_v2_workload_ir_is_typed_hashed_and_semantically_canonical() -> None:
    yaml_spec = """
version: mws-0.1
name: api_ir_demo
record_count: 1000
fields:
  - name: id
    type: uint64
    cardinality: 1000
  - name: age
    type: uint32
    cardinality: 80
queries:
  - kind: point_lookup
    field: id
    weight: 3
  - kind: range_scan
    field: age
    weight: 1
""".strip()
    first = client.post("/api/v2/workload/ir", json={"spec_text": yaml_spec})
    assert first.status_code == 200
    payload = first.json()
    assert len(payload["workload_ir_hash"]) == 64
    assert payload["workload_ir"]["ir_version"] == "morpheus-workload-ir-v2"
    assert payload["workload_ir"]["fields"][0]["id"] == "f0:id"
    assert payload["workload_ir"]["operations"][0]["normalized_weight"] == 0.75
    assert payload["workload_ir"]["operations"][1]["normalized_weight"] == 0.25
    assert payload["workload_ir"]["operations"][0]["distribution"]["kind"] == "uniform"
    assert payload["workload_ir"]["operations"][1]["distribution"]["kind"] == "uniform"
    assert payload["evidence_state"] == "DETERMINISTIC_SEMANTIC_LOWERING"

    # Equivalent JSON formatting lowers to the exact same semantic IR identity.
    equivalent_json = (
        '{"version":"mws-0.1","name":"api_ir_demo","record_count":1000,'
        '"fields":[{"name":"id","type":"uint64","cardinality":1000},'
        '{"name":"age","type":"uint32","cardinality":80}],'
        '"queries":[{"kind":"point_lookup","field":"id","weight":3},'
        '{"kind":"range_scan","field":"age","weight":1}]}'
    )
    second = client.post("/api/v2/workload/ir", json={"spec_text": equivalent_json})
    assert second.status_code == 200
    assert second.json()["workload_ir_hash"] == payload["workload_ir_hash"]


def test_v2_grouped_heldout_evaluation_is_explicitly_caller_supplied() -> None:
    response = client.post(
        "/api/v2/research/heldout/evaluate",
        json={
            "measurements": [
                {"workload_id": "w1", "candidate_id": "a", "predicted": 1.0, "measured": 1.1},
                {"workload_id": "w1", "candidate_id": "b", "predicted": 2.0, "measured": 2.0},
                {"workload_id": "w2", "candidate_id": "a", "predicted": 1.0, "measured": 3.0},
                {"workload_id": "w2", "candidate_id": "b", "predicted": 1.5, "measured": 1.0},
            ],
            "top_k": 1,
            "bootstrap_rounds": 200,
            "bootstrap_seed": 9,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["evidence_state"] == "HELDOUT_EVALUATION_CALLER_SUPPLIED_MEASUREMENTS"
    assert payload["report"]["workload_count"] == 2
    assert payload["report"]["oracle_hit_rate"] == 0.5
    assert "does not certify" in payload["truth_boundary"]


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
