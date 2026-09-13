from __future__ import annotations

import json
from copy import deepcopy

from fastapi.testclient import TestClient

import app.startup_mvp_api as startup_mvp_api
from app.advanced_api import capabilities_v2_payload
from app.feature_registry import registry_payload
from app.pilot_capabilities import pilot_capabilities_payload
from app.server import app
from app.startup_readiness import build_startup_mvp_readiness


_LOCAL_IDS = (
    "durable_state_store",
    "content_addressed_artifact_store",
    "evidence_ledger_integrity",
    "durable_idempotency_journal",
    "no_ambiguous_idempotency_side_effects",
    "native_cpp20_toolchain",
)


def _pilot_report(*, configuration_ready: bool, failed_local: str | None = None) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    for check_id in _LOCAL_IDS:
        passed = check_id != failed_local
        checks.append(
            {
                "id": check_id,
                "required": True,
                "passed": passed,
                "detail": f"synthetic {check_id} {'ready' if passed else 'blocked'}",
                "evidence_state": f"TEST_{check_id.upper()}",
            }
        )
    for check_id in ("api_key_guard", "request_rate_limit"):
        checks.append(
            {
                "id": check_id,
                "required": True,
                "passed": configuration_ready,
                "detail": f"synthetic {check_id}",
                "evidence_state": f"TEST_{check_id.upper()}",
            }
        )
    checks.append(
        {
            "id": "active_calibration_profile",
            "required": False,
            "passed": False,
            "detail": "synthetic calibration advisory",
            "evidence_state": "TEST_CALIBRATION_ADVISORY",
        }
    )
    blockers = [str(item["id"]) for item in checks if item["required"] and not item["passed"]]
    return {
        "schema": "morpheus-pilot-readiness-v1",
        "ready": not blockers,
        "state": "PILOT_READY_SINGLE_NODE_SCOPE" if not blockers else "PILOT_NOT_READY",
        "checks": checks,
        "blockers": blockers,
        "advisories": ["active_calibration_profile"],
    }


def _diagnostics() -> dict[str, object]:
    return {
        "python": "3.14.0",
        "python_executable": "/not/exposed/python",
        "platform": "Test",
        "system": "Linux",
        "machine": "x86_64",
        "processor": "test",
        "toolchain": {
            "kind": "gnu",
            "executable": "/not/exposed/g++",
            "version": "g++ test 1",
        },
        "executables": {},
        "morpheus_cxx_override": None,
        "evidence_state": "LOCAL_ENVIRONMENT_DIAGNOSTIC",
    }


def _build(*, configuration_ready: bool = False, failed_local: str | None = None, registry=None, pilot_capabilities=None):
    return build_startup_mvp_readiness(
        capabilities=capabilities_v2_payload(),
        feature_registry=registry if registry is not None else registry_payload(),
        pilot_readiness=_pilot_report(configuration_ready=configuration_ready, failed_local=failed_local),
        pilot_capabilities=pilot_capabilities if pilot_capabilities is not None else pilot_capabilities_payload(),
        diagnostics=_diagnostics(),
        api_contract_sha256="a" * 64,
        api_route_count=64,
    )


def _canonical_payload(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _install_endpoint_fixture(monkeypatch, *, registry: dict[str, object] | None = None, contract_sha256: str = "a" * 64) -> None:
    contract = {"paths": {f"/fixture/{index}": {} for index in range(64)}}
    monkeypatch.setattr(startup_mvp_api, "capabilities_v2_payload", capabilities_v2_payload)
    monkeypatch.setattr(startup_mvp_api, "registry_payload", lambda: deepcopy(registry if registry is not None else registry_payload()))
    monkeypatch.setattr(startup_mvp_api, "build_pilot_readiness", lambda: _pilot_report(configuration_ready=False))
    monkeypatch.setattr(startup_mvp_api, "pilot_capabilities_payload", pilot_capabilities_payload)
    monkeypatch.setattr(startup_mvp_api, "system_diagnostics", _diagnostics)
    monkeypatch.setattr(startup_mvp_api, "openapi_contract_fingerprint", lambda _schema: (deepcopy(contract), contract_sha256))


def test_local_startup_mvp_can_be_ready_while_protected_pilot_configuration_is_pending() -> None:
    report = _build(configuration_ready=False)

    assert report["ready"] is True
    assert report["startup_mvp_percent"] == 100.0
    assert report["blockers"] == []
    assert report["pilot_ready"] is False
    assert set(report["pilot_configuration_blockers"]) == {"api_key_guard", "request_rate_limit"}
    assert report["state"] == "STARTUP_MVP_READY_LOCAL_PILOT_CONFIGURATION_PENDING"
    assert report["engineering_completion"]["percent"] == 100.0
    assert report["scope"]["production_deployment_authorized"] is False
    assert report["scope"]["automatic_control_allowed"] is False
    assert len(report["readiness_sha256"]) == 64


def test_guarded_single_node_pilot_is_a_stronger_state_than_local_mvp() -> None:
    report = _build(configuration_ready=True)

    assert report["ready"] is True
    assert report["pilot_ready"] is True
    assert report["pilot_blockers"] == []
    assert report["state"] == "STARTUP_MVP_READY_GUARDED_SINGLE_NODE_PILOT"


def test_local_startup_mvp_fails_closed_when_evidence_ledger_integrity_is_missing() -> None:
    report = _build(configuration_ready=True, failed_local="evidence_ledger_integrity")

    assert report["ready"] is False
    assert report["pilot_ready"] is False
    assert report["startup_mvp_percent"] < 100.0
    assert "evidence_ledger_integrity" in report["blockers"]
    assert report["state"] == "STARTUP_MVP_NOT_READY"


def test_startup_mvp_fails_closed_for_unsafe_feature_policy() -> None:
    registry = deepcopy(registry_payload())
    blocked = next(item for item in registry["features"] if item["id"] == "native_cross_process_hot_swap")
    blocked["default_enabled"] = True

    report = _build(configuration_ready=True, registry=registry)

    assert report["ready"] is False
    assert "feature_policy_integrity" in report["blockers"]
    assert report["unsafe_feature_policy_findings"] == ["native_cross_process_hot_swap:blocked_default_enabled"]


def test_startup_mvp_requires_declared_single_node_hardening_capabilities() -> None:
    pilot_capabilities = deepcopy(pilot_capabilities_payload())
    pilot_capabilities["capabilities"]["single_node_backup_restore"] = "NOT_IMPLEMENTED"

    report = _build(configuration_ready=True, pilot_capabilities=pilot_capabilities)

    assert report["ready"] is False
    assert "startup_pilot_capability_integrity" in report["blockers"]
    assert report["missing_required_pilot_capabilities"] == ["single_node_backup_restore"]


def test_startup_mvp_readiness_hash_is_deterministic_for_identical_inputs() -> None:
    first = _build(configuration_ready=False)
    second = _build(configuration_ready=False)
    assert first["readiness_sha256"] == second["readiness_sha256"]


def test_startup_mvp_readiness_api_exposes_scoped_state_without_secret_or_path_details() -> None:
    client = TestClient(app)
    first = client.get("/api/v2/system/startup-mvp-readiness")
    second = client.get("/api/v2/system/startup-mvp-readiness")

    assert first.status_code == 200
    assert second.status_code == 200
    payload = first.json()
    assert payload["schema"] == "morpheus-startup-mvp-readiness-v1"
    assert payload["state"] in {
        "STARTUP_MVP_NOT_READY",
        "STARTUP_MVP_READY_LOCAL_PILOT_CONFIGURATION_PENDING",
        "STARTUP_MVP_READY_LOCAL_PILOT_HARDENING_PENDING",
        "STARTUP_MVP_READY_GUARDED_SINGLE_NODE_PILOT",
    }
    assert isinstance(payload["ready"], bool)
    assert 0.0 <= payload["startup_mvp_percent"] <= 100.0
    assert payload["engineering_completion"]["percent"] == 100.0
    assert payload["scope"]["production_deployment_authorized"] is False
    assert payload["scope"]["automatic_control_allowed"] is False
    assert len(payload["readiness_sha256"]) == 64
    assert payload["readiness_sha256"] == second.json()["readiness_sha256"]

    serialized = first.text
    assert "MORPHEUS_API_KEY" not in serialized
    assert "MORPHEUS_RATE_LIMIT_PER_MINUTE" not in serialized
    assert "python_executable" not in serialized
    assert "artifact_root" not in serialized
    assert "/home/" not in serialized
    assert "\\\\Users\\\\" not in serialized

    paths = app.openapi()["paths"]
    assert "/api/v2/system/startup-mvp-readiness" in paths


def test_public_startup_readiness_is_byte_reproducible_for_unchanged_declared_inputs(monkeypatch) -> None:
    _install_endpoint_fixture(monkeypatch)
    client = TestClient(app)

    first = client.get("/api/v2/system/startup-mvp-readiness")
    second = client.get("/api/v2/system/startup-mvp-readiness")

    assert first.status_code == 200
    assert second.status_code == 200
    first_payload = first.json()
    second_payload = second.json()
    assert _canonical_payload(first_payload) == _canonical_payload(second_payload)
    assert first_payload["readiness_sha256"] == second_payload["readiness_sha256"]
    assert first_payload["state"] == "STARTUP_MVP_READY_LOCAL_PILOT_CONFIGURATION_PENDING"
    assert first_payload["scope"]["production_deployment_authorized"] is False
    assert first_payload["scope"]["automatic_control_allowed"] is False


def test_public_startup_readiness_policy_drift_changes_semantics_and_digest_fail_closed(monkeypatch) -> None:
    _install_endpoint_fixture(monkeypatch)
    client = TestClient(app)
    baseline = client.get("/api/v2/system/startup-mvp-readiness").json()

    drifted_registry = deepcopy(registry_payload())
    blocked = next(item for item in drifted_registry["features"] if item["id"] == "native_cross_process_hot_swap")
    blocked["default_enabled"] = True
    monkeypatch.setattr(startup_mvp_api, "registry_payload", lambda: deepcopy(drifted_registry))
    drifted = client.get("/api/v2/system/startup-mvp-readiness").json()

    assert baseline["state"] == "STARTUP_MVP_READY_LOCAL_PILOT_CONFIGURATION_PENDING"
    assert drifted["state"] == "STARTUP_MVP_NOT_READY"
    assert "feature_policy_integrity" in drifted["blockers"]
    assert drifted["readiness_sha256"] != baseline["readiness_sha256"]
    assert drifted["scope"]["production_deployment_authorized"] is False
    assert drifted["scope"]["automatic_control_allowed"] is False


def test_public_startup_readiness_api_contract_drift_changes_semantics_and_digest_fail_closed(monkeypatch) -> None:
    _install_endpoint_fixture(monkeypatch)
    client = TestClient(app)
    baseline = client.get("/api/v2/system/startup-mvp-readiness").json()

    contract = {"paths": {f"/fixture/{index}": {} for index in range(64)}}
    monkeypatch.setattr(startup_mvp_api, "openapi_contract_fingerprint", lambda _schema: (deepcopy(contract), "invalid-contract-digest"))
    drifted = client.get("/api/v2/system/startup-mvp-readiness").json()

    assert baseline["state"] == "STARTUP_MVP_READY_LOCAL_PILOT_CONFIGURATION_PENDING"
    assert drifted["state"] == "STARTUP_MVP_NOT_READY"
    assert "api_contract_identity" in drifted["blockers"]
    assert drifted["readiness_sha256"] != baseline["readiness_sha256"]
    assert drifted["scope"]["production_deployment_authorized"] is False
    assert drifted["scope"]["automatic_control_allowed"] is False
