from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.server import app
from app.startup_readiness_evidence import (
    TRANSITION_CHANGED_DRIFT,
    TRANSITION_COHERENT_TO_DRIFTED,
    TRANSITION_DRIFTED_TO_COHERENT,
    TRANSITION_UNCHANGED_COHERENT,
    build_startup_readiness_coherence_transition,
    build_startup_readiness_evidence,
    compare_startup_readiness_evidence_to_current,
    verify_startup_readiness_coherence_transition,
)


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _readdress_readiness(readiness: dict[str, object]) -> dict[str, object]:
    core = {key: value for key, value in readiness.items() if key != "readiness_sha256"}
    return {**core, "readiness_sha256": _canonical_sha256(core)}


def _readdress_transition(transition: dict[str, object]) -> dict[str, object]:
    core = {key: value for key, value in transition.items() if key != "transition_sha256"}
    return {**core, "transition_sha256": _canonical_sha256(core)}


def _current_readiness() -> dict[str, object]:
    response = TestClient(app).get("/api/v2/system/startup-mvp-readiness")
    assert response.status_code == 200
    return response.json()


def _coherent_report(current: dict[str, object]) -> dict[str, object]:
    return compare_startup_readiness_evidence_to_current(build_startup_readiness_evidence(current), current)


def _drifted_report(current: dict[str, object], section: str, field: str, value: str) -> dict[str, object]:
    historical = deepcopy(current)
    historical[section][field] = value
    historical = _readdress_readiness(historical)
    return compare_startup_readiness_evidence_to_current(build_startup_readiness_evidence(historical), current)


def test_transition_replays_deterministically_for_unchanged_coherent_reports() -> None:
    current = _current_readiness()
    report = _coherent_report(current)

    first = build_startup_readiness_coherence_transition(report, report)
    second = build_startup_readiness_coherence_transition(report, report)

    assert first == second
    assert first["transition_kind"] == TRANSITION_UNCHANGED_COHERENT
    assert first["before_coherence_sha256"] == report["coherence_sha256"]
    assert first["after_coherence_sha256"] == report["coherence_sha256"]
    assert first["transition_sha256"] == _canonical_sha256(
        {key: value for key, value in first.items() if key != "transition_sha256"}
    )
    assert verify_startup_readiness_coherence_transition(first) == first
    assert first["authority"] == {
        "production_deployment_authorized": False,
        "automatic_control_allowed": False,
        "activation_allowed": False,
    }


def test_transition_classifies_coherent_to_drifted_and_back() -> None:
    current = _current_readiness()
    coherent = _coherent_report(current)
    drifted = _drifted_report(current, "environment", "system", "historical-system")

    into_drift = build_startup_readiness_coherence_transition(coherent, drifted)
    out_of_drift = build_startup_readiness_coherence_transition(drifted, coherent)

    assert into_drift["transition_kind"] == TRANSITION_COHERENT_TO_DRIFTED
    assert out_of_drift["transition_kind"] == TRANSITION_DRIFTED_TO_COHERENT
    verify_startup_readiness_coherence_transition(into_drift)
    verify_startup_readiness_coherence_transition(out_of_drift)


def test_transition_distinguishes_changed_drift_content() -> None:
    current = _current_readiness()
    environment_drift = _drifted_report(current, "environment", "system", "historical-system")
    scope_drift = _drifted_report(current, "scope", "readiness_target", "HISTORICAL_LOCAL_STARTUP_MVP")

    transition = build_startup_readiness_coherence_transition(environment_drift, scope_drift)

    assert transition["transition_kind"] == TRANSITION_CHANGED_DRIFT
    assert transition["before_coherence_sha256"] != transition["after_coherence_sha256"]
    verify_startup_readiness_coherence_transition(transition)


def test_transition_digest_tampering_is_rejected() -> None:
    current = _current_readiness()
    report = _coherent_report(current)
    transition = build_startup_readiness_coherence_transition(report, report)
    tampered = deepcopy(transition)
    tampered["transition_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="digest does not match"):
        verify_startup_readiness_coherence_transition(tampered)


def test_readdressed_transition_kind_forgery_is_rejected() -> None:
    current = _current_readiness()
    coherent = _coherent_report(current)
    drifted = _drifted_report(current, "environment", "system", "historical-system")
    transition = build_startup_readiness_coherence_transition(coherent, drifted)
    forged = deepcopy(transition)
    forged["transition_kind"] = TRANSITION_DRIFTED_TO_COHERENT
    forged = _readdress_transition(forged)

    with pytest.raises(ValueError, match="kind is inconsistent"):
        verify_startup_readiness_coherence_transition(forged)


def test_readdressed_authority_escalation_is_rejected() -> None:
    current = _current_readiness()
    report = _coherent_report(current)
    transition = build_startup_readiness_coherence_transition(report, report)
    forged = deepcopy(transition)
    forged["authority"]["activation_allowed"] = True
    forged = _readdress_transition(forged)

    with pytest.raises(ValueError, match="cannot carry activation authority"):
        verify_startup_readiness_coherence_transition(forged)


def test_nested_coherence_tampering_is_rejected_even_if_transition_is_readdressed() -> None:
    current = _current_readiness()
    report = _coherent_report(current)
    transition = build_startup_readiness_coherence_transition(report, report)
    forged = deepcopy(transition)
    forged["after"]["coherence_sha256"] = "0" * 64
    forged["after_coherence_sha256"] = "0" * 64
    forged = _readdress_transition(forged)

    with pytest.raises(ValueError, match="coherence digest does not match"):
        verify_startup_readiness_coherence_transition(forged)


def test_readdressed_missing_truth_boundaries_are_rejected() -> None:
    current = _current_readiness()
    report = _coherent_report(current)
    transition = build_startup_readiness_coherence_transition(report, report)
    forged = deepcopy(transition)
    forged["truth_boundaries"] = []
    forged = _readdress_transition(forged)

    with pytest.raises(ValueError, match="truth boundaries are missing"):
        verify_startup_readiness_coherence_transition(forged)
