from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.server import app
from app.startup_readiness_evidence import (
    CURRENT_COHERENT_STATE,
    CURRENT_DRIFTED_STATE,
    build_startup_readiness_evidence,
    compare_startup_readiness_evidence_to_current,
    verify_startup_readiness_current_coherence,
)


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _readdress_readiness(readiness: dict[str, object]) -> dict[str, object]:
    core = {key: value for key, value in readiness.items() if key != "readiness_sha256"}
    return {**core, "readiness_sha256": _canonical_sha256(core)}


def _readdress_report(report: dict[str, object]) -> dict[str, object]:
    core = {key: value for key, value in report.items() if key != "coherence_sha256"}
    return {**core, "coherence_sha256": _canonical_sha256(core)}


def _current_readiness() -> dict[str, object]:
    response = TestClient(app).get("/api/v2/system/startup-mvp-readiness")
    assert response.status_code == 200
    return response.json()


def test_current_coherence_report_replays_deterministically() -> None:
    client = TestClient(app)
    first = client.get("/api/v2/system/startup-mvp-readiness/evidence/current-coherence")
    second = client.get("/api/v2/system/startup-mvp-readiness/evidence/current-coherence")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()

    report = first.json()
    verified = verify_startup_readiness_current_coherence(report)
    assert verified == report
    assert report["evidence_state"] == CURRENT_COHERENT_STATE
    assert report["matches_current"] is True
    assert report["coherence_sha256"] == _canonical_sha256(
        {key: value for key, value in report.items() if key != "coherence_sha256"}
    )
    assert report["authority"] == {
        "production_deployment_authorized": False,
        "automatic_control_allowed": False,
        "activation_allowed": False,
    }


def test_digest_tampering_is_rejected() -> None:
    current = _current_readiness()
    report = compare_startup_readiness_evidence_to_current(build_startup_readiness_evidence(current), current)
    tampered = deepcopy(report)
    tampered["coherence_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="digest does not match"):
        verify_startup_readiness_current_coherence(tampered)


def test_readdressed_false_coherent_semantics_are_rejected() -> None:
    current = _current_readiness()
    historical = deepcopy(current)
    historical["environment"]["system"] = "historical-system"
    historical = _readdress_readiness(historical)
    report = compare_startup_readiness_evidence_to_current(build_startup_readiness_evidence(historical), current)

    assert report["evidence_state"] == CURRENT_DRIFTED_STATE
    forged = deepcopy(report)
    forged["matches_current"] = True
    forged["evidence_state"] = CURRENT_COHERENT_STATE
    forged = _readdress_report(forged)

    with pytest.raises(ValueError, match="inconsistent readiness identities"):
        verify_startup_readiness_current_coherence(forged)


def test_readdressed_authority_escalation_is_rejected() -> None:
    current = _current_readiness()
    report = compare_startup_readiness_evidence_to_current(build_startup_readiness_evidence(current), current)
    forged = deepcopy(report)
    forged["authority"]["automatic_control_allowed"] = True
    forged = _readdress_report(forged)

    with pytest.raises(ValueError, match="cannot carry activation authority"):
        verify_startup_readiness_current_coherence(forged)


def test_readdressed_drift_report_requires_nonempty_classification() -> None:
    current = _current_readiness()
    historical = deepcopy(current)
    historical["scope"]["readiness_target"] = "HISTORICAL_LOCAL_STARTUP_MVP"
    historical = _readdress_readiness(historical)
    report = compare_startup_readiness_evidence_to_current(build_startup_readiness_evidence(historical), current)
    forged = deepcopy(report)
    forged["drifted_sections"] = []
    forged = _readdress_report(forged)

    with pytest.raises(ValueError, match="inconsistent readiness identities"):
        verify_startup_readiness_current_coherence(forged)
