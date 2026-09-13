from __future__ import annotations

import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.server import app
from app.startup_readiness_evidence import (
    EVIDENCE_STATE,
    SCHEMA,
    verify_startup_readiness_evidence,
)


def _canonical(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def test_public_startup_readiness_evidence_is_deterministic_and_replayable() -> None:
    client = TestClient(app)

    first = client.get("/api/v2/system/startup-mvp-readiness/evidence")
    second = client.get("/api/v2/system/startup-mvp-readiness/evidence")

    assert first.status_code == 200
    assert second.status_code == 200
    first_payload = first.json()
    second_payload = second.json()
    assert _canonical(first_payload) == _canonical(second_payload)
    assert first_payload["schema"] == SCHEMA
    assert first_payload["evidence_state"] == EVIDENCE_STATE
    assert first_payload["readiness_sha256"] == first_payload["readiness"]["readiness_sha256"]
    assert first_payload["authority"] == {
        "production_deployment_authorized": False,
        "automatic_control_allowed": False,
        "activation_allowed": False,
    }
    assert verify_startup_readiness_evidence(first_payload) == first_payload

    paths = app.openapi()["paths"]
    assert "/api/v2/system/startup-mvp-readiness/evidence" in paths


def test_startup_readiness_evidence_rejects_embedded_payload_tampering() -> None:
    payload = TestClient(app).get("/api/v2/system/startup-mvp-readiness/evidence").json()
    tampered = deepcopy(payload)
    tampered["readiness"]["state"] = "STARTUP_MVP_READY_GUARDED_SINGLE_NODE_PILOT"

    with pytest.raises(ValueError, match="startup readiness digest"):
        verify_startup_readiness_evidence(tampered)


def test_startup_readiness_evidence_rejects_authority_escalation_even_before_digest_replay() -> None:
    payload = TestClient(app).get("/api/v2/system/startup-mvp-readiness/evidence").json()
    tampered = deepcopy(payload)
    tampered["authority"]["automatic_control_allowed"] = True

    with pytest.raises(ValueError, match="cannot carry activation authority"):
        verify_startup_readiness_evidence(tampered)


def test_startup_readiness_evidence_rejects_envelope_digest_tampering() -> None:
    payload = TestClient(app).get("/api/v2/system/startup-mvp-readiness/evidence").json()
    tampered = deepcopy(payload)
    tampered["evidence_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="evidence digest does not match"):
        verify_startup_readiness_evidence(tampered)
