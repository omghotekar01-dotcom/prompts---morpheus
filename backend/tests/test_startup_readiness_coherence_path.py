from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.server import app
from app.startup_readiness_evidence import (
    build_startup_readiness_coherence_transition,
    build_startup_readiness_evidence,
    compare_startup_readiness_evidence_to_current,
)
from app.startup_readiness_path_evidence import (
    build_startup_readiness_coherence_path,
    verify_startup_readiness_coherence_path,
)


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _readdress_readiness(readiness: dict[str, object]) -> dict[str, object]:
    core = {key: value for key, value in readiness.items() if key != "readiness_sha256"}
    return {**core, "readiness_sha256": _canonical_sha256(core)}


def _readdress_path(path: dict[str, object]) -> dict[str, object]:
    core = {key: value for key, value in path.items() if key != "path_sha256"}
    return {**core, "path_sha256": _canonical_sha256(core)}


def _current_readiness() -> dict[str, object]:
    response = TestClient(app).get("/api/v2/system/startup-mvp-readiness")
    assert response.status_code == 200
    return response.json()


def _report(current: dict[str, object], *, system: str | None = None) -> dict[str, object]:
    historical = deepcopy(current)
    if system is not None:
        historical["environment"]["system"] = system
        historical = _readdress_readiness(historical)
    evidence = build_startup_readiness_evidence(historical)
    return compare_startup_readiness_evidence_to_current(evidence, current)


def test_path_replays_deterministically_for_continuous_multi_transition_input() -> None:
    current = _current_readiness()
    coherent = _report(current)
    drifted = _report(current, system="historical-system")
    into_drift = build_startup_readiness_coherence_transition(coherent, drifted)
    out_of_drift = build_startup_readiness_coherence_transition(drifted, coherent)

    first = build_startup_readiness_coherence_path([into_drift, out_of_drift])
    second = build_startup_readiness_coherence_path([into_drift, out_of_drift])

    assert first == second
    assert first["transition_count"] == 2
    assert first["starts_coherent"] is True
    assert first["ends_coherent"] is True
    assert first["contains_declared_drift"] is True
    assert first["coherence_state_change_count"] == 2
    assert first["start_coherence_sha256"] == coherent["coherence_sha256"]
    assert first["end_coherence_sha256"] == coherent["coherence_sha256"]
    assert first["path_sha256"] == _canonical_sha256({key: value for key, value in first.items() if key != "path_sha256"})
    assert verify_startup_readiness_coherence_path(first) == first


def test_path_rejects_broken_adjacency_continuity() -> None:
    current = _current_readiness()
    coherent = _report(current)
    drift_a = _report(current, system="historical-system-a")
    drift_b = _report(current, system="historical-system-b")
    first = build_startup_readiness_coherence_transition(coherent, drift_a)
    disconnected = build_startup_readiness_coherence_transition(drift_b, coherent)

    with pytest.raises(ValueError, match="broken adjacency continuity"):
        build_startup_readiness_coherence_path([first, disconnected])


def test_path_rejects_duplicate_transition_identity() -> None:
    current = _current_readiness()
    coherent = _report(current)
    unchanged = build_startup_readiness_coherence_transition(coherent, coherent)

    with pytest.raises(ValueError, match="duplicate transition identities"):
        build_startup_readiness_coherence_path([unchanged, unchanged])


def test_path_rejects_nested_transition_tampering() -> None:
    current = _current_readiness()
    coherent = _report(current)
    drifted = _report(current, system="historical-system")
    into_drift = build_startup_readiness_coherence_transition(coherent, drifted)
    out_of_drift = build_startup_readiness_coherence_transition(drifted, coherent)
    path = build_startup_readiness_coherence_path([into_drift, out_of_drift])
    forged = deepcopy(path)
    forged["transitions"][1]["transition_sha256"] = "0" * 64
    forged = _readdress_path(forged)

    with pytest.raises(ValueError, match="transition digest does not match"):
        verify_startup_readiness_coherence_path(forged)


def test_path_rejects_readdressed_semantic_summary_forgery() -> None:
    current = _current_readiness()
    coherent = _report(current)
    drifted = _report(current, system="historical-system")
    into_drift = build_startup_readiness_coherence_transition(coherent, drifted)
    out_of_drift = build_startup_readiness_coherence_transition(drifted, coherent)
    path = build_startup_readiness_coherence_path([into_drift, out_of_drift])
    forged = deepcopy(path)
    forged["contains_declared_drift"] = False
    forged = _readdress_path(forged)

    with pytest.raises(ValueError, match="contains_declared_drift is inconsistent"):
        verify_startup_readiness_coherence_path(forged)


def test_path_rejects_readdressed_authority_escalation() -> None:
    current = _current_readiness()
    coherent = _report(current)
    drifted = _report(current, system="historical-system")
    into_drift = build_startup_readiness_coherence_transition(coherent, drifted)
    out_of_drift = build_startup_readiness_coherence_transition(drifted, coherent)
    path = build_startup_readiness_coherence_path([into_drift, out_of_drift])
    forged = deepcopy(path)
    forged["authority"]["automatic_control_allowed"] = True
    forged = _readdress_path(forged)

    with pytest.raises(ValueError, match="cannot carry activation authority"):
        verify_startup_readiness_coherence_path(forged)
