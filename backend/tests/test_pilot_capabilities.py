from __future__ import annotations

from fastapi.testclient import TestClient

from app.pilot_capabilities import pilot_capabilities_payload
from app.server import app


client = TestClient(app)


def test_pilot_capability_ledger_is_deterministic_and_scope_qualified() -> None:
    first = pilot_capabilities_payload()
    second = pilot_capabilities_payload()
    assert first == second
    assert first["schema"] == "morpheus-startup-pilot-capabilities-v1"
    assert first["declared_scope"] == "SINGLE_NODE_ENGINEERING_PILOT"
    assert first["production_deployment_authorized"] is False
    assert len(first["sha256"]) == 64

    capabilities = first["capabilities"]
    assert capabilities["fail_closed_pilot_readiness"] == "IMPLEMENTED_TESTED_LOCAL_PREFLIGHT"
    assert capabilities["durable_idempotent_pilot_synthesis"].endswith("NOT_DISTRIBUTED_EXACTLY_ONCE")
    assert capabilities["automatic_retry_execution_authority"] == "NOT_GRANTED_BY_EVIDENCE_UTILITIES"
    assert capabilities["native_cross_process_hot_swap"] == "BLOCKED_NOT_IMPLEMENTED"
    assert capabilities["high_availability_storage"].startswith("NOT_IMPLEMENTED")
    assert any("single-node" in boundary.lower() for boundary in first["truth_boundaries"])


def test_pilot_capability_api_is_part_of_versioned_system_contract() -> None:
    response = client.get("/api/v2/system/pilot-capabilities")
    assert response.status_code == 200
    payload = response.json()
    assert payload == pilot_capabilities_payload()

    contract = client.get("/api/v2/system/schema-contract")
    assert contract.status_code == 200
    assert "/api/v2/system/pilot-capabilities" in contract.json()["contract"]["paths"]
