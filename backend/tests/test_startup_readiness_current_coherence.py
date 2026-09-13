from __future__ import annotations

import hashlib
import json
from copy import deepcopy

from fastapi.testclient import TestClient

from app.server import app
from app.startup_readiness_evidence import (
    CURRENT_COHERENT_STATE,
    CURRENT_COHERENCE_SCHEMA,
    CURRENT_DRIFTED_STATE,
    build_startup_readiness_evidence,
    compare_startup_readiness_evidence_to_current,
    verify_startup_readiness_evidence,
)


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _readdress(readiness: dict[str, object]) -> dict[str, object]:
    core = {key: value for key, value in readiness.items() if key != "readiness_sha256"}
    return {**core, "readiness_sha256": _canonical_sha256(core)}


def test_public_current_coherence_route_is_deterministic_non_authoritative_and_current() -> None:
    client = TestClient(app)
    first = client.get("/api/v2/system/startup-mvp-readiness/evidence/current-coherence")
    second = client.get("/api/v2/system/startup-mvp-readiness/evidence/current-coherence")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    payload = first.json()
    assert payload["schema"] == CURRENT_COHERENCE_SCHEMA
    assert payload["evidence_state"] == CURRENT_COHERENT_STATE
    assert payload["matches_current"] is True
    assert payload["drifted_sections"] == []
    assert payload["embedded_readiness_sha256"] == payload["current_readiness_sha256"]
    assert payload["authority"] == {
        "production_deployment_authorized": False,
        "automatic_control_allowed": False,
        "activation_allowed": False,
    }
    assert "/api/v2/system/startup-mvp-readiness/evidence/current-coherence" in app.openapi()["paths"]


def test_self_consistent_historical_environment_evidence_is_valid_but_not_current() -> None:
    current = TestClient(app).get("/api/v2/system/startup-mvp-readiness").json()
    historical = deepcopy(current)
    historical["environment"]["system"] = "historical-local-system"
    historical = _readdress(historical)
    evidence = build_startup_readiness_evidence(historical)

    assert verify_startup_readiness_evidence(evidence) == evidence
    report = compare_startup_readiness_evidence_to_current(evidence, current)
    assert report["matches_current"] is False
    assert report["evidence_state"] == CURRENT_DRIFTED_STATE
    assert "environment" in report["drifted_sections"]
    assert report["embedded_readiness_sha256"] != report["current_readiness_sha256"]
    assert report["authority"]["automatic_control_allowed"] is False


def test_self_consistent_historical_compatibility_evidence_is_valid_but_not_current() -> None:
    current = TestClient(app).get("/api/v2/system/startup-mvp-readiness").json()
    historical = deepcopy(current)
    historical["compatibility"]["api_contract_sha256"] = "0" * 64
    historical = _readdress(historical)
    evidence = build_startup_readiness_evidence(historical)

    assert verify_startup_readiness_evidence(evidence) == evidence
    report = compare_startup_readiness_evidence_to_current(evidence, current)
    assert report["matches_current"] is False
    assert report["evidence_state"] == CURRENT_DRIFTED_STATE
    assert "compatibility" in report["drifted_sections"]
    assert report["authority"]["production_deployment_authorized"] is False


def test_scope_drift_is_classified_without_turning_coherence_into_authority() -> None:
    current = TestClient(app).get("/api/v2/system/startup-mvp-readiness").json()
    historical = deepcopy(current)
    historical["scope"]["readiness_target"] = "HISTORICAL_LOCAL_SINGLE_USER_STARTUP_MVP"
    historical = _readdress(historical)
    evidence = build_startup_readiness_evidence(historical)

    report = compare_startup_readiness_evidence_to_current(evidence, current)
    assert report["matches_current"] is False
    assert "scope" in report["drifted_sections"]
    assert report["authority"] == {
        "production_deployment_authorized": False,
        "automatic_control_allowed": False,
        "activation_allowed": False,
    }
