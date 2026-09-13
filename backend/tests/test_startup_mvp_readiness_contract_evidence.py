from __future__ import annotations

import json
from copy import deepcopy

from fastapi.testclient import TestClient

from app.advanced_api import capabilities_v2_payload
from app.feature_registry import registry_payload
from app.pilot_capabilities import pilot_capabilities_payload
from app.pilot_readiness import build_pilot_readiness
from app.server import app
from app.startup_readiness import build_startup_mvp_readiness
from app.toolchain import system_diagnostics


def _canonical_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _build(*, feature_registry=None, api_contract_sha256: str = "a" * 64) -> dict[str, object]:
    return build_startup_mvp_readiness(
        capabilities=capabilities_v2_payload(),
        feature_registry=feature_registry if feature_registry is not None else registry_payload(),
        pilot_readiness=build_pilot_readiness(),
        pilot_capabilities=pilot_capabilities_payload(),
        diagnostics=system_diagnostics(),
        api_contract_sha256=api_contract_sha256,
        api_route_count=64,
    )


def test_public_startup_readiness_is_byte_reproducible_for_unchanged_state() -> None:
    client = TestClient(app)

    first = client.get("/api/v2/system/startup-mvp-readiness")
    second = client.get("/api/v2/system/startup-mvp-readiness")

    assert first.status_code == 200
    assert second.status_code == 200
    first_payload = first.json()
    second_payload = second.json()
    assert _canonical_bytes(first_payload) == _canonical_bytes(second_payload)
    assert first_payload["readiness_sha256"] == second_payload["readiness_sha256"]


def test_api_contract_identity_drift_fails_closed_and_changes_readiness_digest() -> None:
    baseline = _build()
    drifted = _build(api_contract_sha256="not-a-sha256")

    assert baseline["readiness_sha256"] != drifted["readiness_sha256"]
    assert "api_contract_identity" in drifted["blockers"]
    assert drifted["ready"] is False
    assert drifted["state"] == "STARTUP_MVP_NOT_READY"
    assert drifted["scope"]["production_deployment_authorized"] is False
    assert drifted["scope"]["automatic_control_allowed"] is False


def test_feature_policy_authority_drift_fails_closed_and_changes_readiness_digest() -> None:
    baseline = _build()
    registry = deepcopy(registry_payload())
    blocked = next(item for item in registry["features"] if item["id"] == "native_cross_process_hot_swap")
    blocked["default_enabled"] = True

    drifted = _build(feature_registry=registry)

    assert baseline["readiness_sha256"] != drifted["readiness_sha256"]
    assert "feature_policy_integrity" in drifted["blockers"]
    assert drifted["unsafe_feature_policy_findings"] == ["native_cross_process_hot_swap:blocked_default_enabled"]
    assert drifted["ready"] is False
    assert drifted["state"] == "STARTUP_MVP_NOT_READY"
    assert drifted["scope"]["production_deployment_authorized"] is False
    assert drifted["scope"]["automatic_control_allowed"] is False
