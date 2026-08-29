from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.dataplane import DATA_PLANE
from app.server import app


client = TestClient(app)
REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "examples" / "users-demo.yaml"


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
    assert payload["feature_policy_registry"] == "IMPLEMENTED_TESTED_FAIL_CLOSED_PROMOTION"
    assert payload["feature_policy_fingerprint"] == "IMPLEMENTED_TESTED_CANONICAL_SHA256"
    assert payload["api_contract_fingerprint"] == "IMPLEMENTED_TESTED_ROUTE_FINGERPRINT"
    assert payload["distribution_bound_calibration"].startswith("IMPLEMENTED_TESTED_EXACT_")
    assert payload["distribution_calibration_matrix"].startswith("IMPLEMENTED_TESTED_CI_SMOKE")
    assert payload["workload_calibration_coverage"] == "IMPLEMENTED_TESTED_FAIL_CLOSED_SCALE_DISTRIBUTION"
    assert payload["distribution_aware_mutation_cost"] == "IMPLEMENTED_TESTED_EXACT_OPERATION_DISTRIBUTION"
    assert payload["distribution_release_provenance"] == "IMPLEMENTED_TESTED_STRUCTURAL_AND_CROSS_HASH_VALIDATION"
    assert payload["contract_bound_reproducibility"] == "IMPLEMENTED_TESTED_EXACT_COMMIT_API_FEATURE_POLICY_HASHES"
    assert payload["prompt_corpus_integrity"] == "IMPLEMENTED_TESTED_39_CANONICAL_PROMPTS"
    assert payload["generated_migration_bundle"] == "IMPLEMENTED_TESTED_GENERATED_PROVENANCE_BOUND"
    assert payload["generated_migration_execution_gate"] == "IMPLEMENTED_TESTED_CROSS_PLATFORM_LOCAL_TOOLCHAIN"
    assert payload["generated_migration_release_evidence"] == "IMPLEMENTED_TESTED_FAIL_CLOSED_NARROW_CLAIM"
    assert payload["local_dataplane_swap"] == "IMPLEMENTED_TESTED_IN_PROCESS"
    assert payload["runtime_hot_swap"] == "NOT_IMPLEMENTED_NATIVE_CROSS_PROCESS"

    completion = client.get("/api/v2/completion")
    assert completion.status_code == 200
    report = completion.json()
    assert report["engineering_percent"] == 100.0
    assert report["passed_gates"] == report["total_gates"]
    assert "publication acceptance" in report["excluded_outcomes"]
    p4 = next(phase for phase in report["phases"] if phase["id"] == "P4")
    p11 = next(phase for phase in report["phases"] if phase["id"] == "P11")
    p12 = next(phase for phase in report["phases"] if phase["id"] == "P12")
    assert p4["state"] == "ENGINEERING_GATES_COMPLETE"
    assert p11["state"] == "ENGINEERING_GATES_COMPLETE"
    assert p12["state"] == "ENGINEERING_GATES_COMPLETE"
    assert p12["gates"][0]["capability"] == "prompt_corpus_integrity"


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


def test_v2_generated_migration_bundle_is_provenance_bound_not_execution_evidence() -> None:
    spec_text = EXAMPLE.read_text(encoding="utf-8")
    response = client.post(
        "/api/v2/migration/generated/bundle",
        json={
            "spec_text": spec_text,
            "record_count": 32,
            "include_sources": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "morpheus-generated-migration-bundle-v1"
    assert payload["source_candidate_id"] != payload["target_candidate_id"]
    assert payload["source_manifest"]["workload_ir_hash"] == payload["target_manifest"]["workload_ir_hash"]
    assert payload["source_manifest"]["configuration_ir_hash"] != payload["target_manifest"]["configuration_ir_hash"]
    assert len(payload["harness_sha256"]) == 64
    assert payload["record_count"] == 32
    assert payload["evidence_state"] == "GENERATED_MIGRATION_BUNDLE_NOT_COMPILE_VERIFIED"
    assert "harness_source" not in payload
    assert "not runtime or performance evidence" in payload["truth_boundary"]

    same_candidate = client.post(
        "/api/v2/migration/generated/bundle",
        json={
            "spec_text": spec_text,
            "source_candidate_id": payload["source_candidate_id"],
            "target_candidate_id": payload["source_candidate_id"],
            "include_sources": False,
        },
    )
    assert same_candidate.status_code == 422
    assert "distinct" in same_candidate.json()["detail"]


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
