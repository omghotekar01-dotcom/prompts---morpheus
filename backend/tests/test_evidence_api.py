from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.toolchain import discover_toolchain


SPEC = """
version: mws-0.1
name: evidence_api
record_count: 1000
fields:
  - name: id
    type: uint64
    cardinality: 1000
  - name: age
    type: uint32
    cardinality: 100
queries:
  - kind: point_lookup
    field: id
    weight: 0.5
  - kind: range_scan
    field: age
    weight: 0.5
    selectivity: 0.2
constraints:
  memory_mb: 32
""".strip()


def test_diagnostics_and_evidence_ledger_are_exposed_without_fabricated_status() -> None:
    client = TestClient(app)
    diagnostics = client.get("/api/system/diagnostics")
    assert diagnostics.status_code == 200
    payload = diagnostics.json()
    assert payload["python"]
    assert payload["evidence_state"] == "LOCAL_ENVIRONMENT_DIAGNOSTIC"

    validated = client.post("/api/validate", json={"spec_text": SPEC})
    assert validated.status_code == 200

    verification = client.get("/api/evidence/verify")
    assert verification.status_code == 200
    assert verification.json()["valid"] is True
    assert verification.json()["entries"] >= 1

    evidence = client.get("/api/evidence?limit=5")
    assert evidence.status_code == 200
    assert evidence.json()
    assert len(evidence.json()[0]["entry_hash"]) == 64


def test_full_artifact_gate_persists_compile_and_behavior_manifest() -> None:
    if discover_toolchain() is None:
        pytest.skip("C++20 compiler unavailable")
    client = TestClient(app)
    response = client.post("/api/artifact/verify/full", json={"spec_text": SPEC})
    assert response.status_code == 200, response.text
    payload = response.json()
    verification = payload["verification"]
    assert verification["success"] is True
    assert verification["evidence_state"] == "FULL_LOCAL_ARTIFACT_GATE_PASSED"
    assert verification["compile_gate"]["success"] is True
    assert verification["behavior_gate"]["success"] is True
    assert verification["behavior_gate"]["checks"] > 0
    assert len(payload["verification_manifest"]["sha256"]) == 64
