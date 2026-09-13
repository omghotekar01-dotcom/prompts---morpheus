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
from app.startup_readiness_path_evidence import build_startup_readiness_coherence_path
from app.startup_readiness_path_extension_evidence import (
    build_startup_readiness_coherence_path_extension,
    verify_startup_readiness_coherence_path_extension,
)


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _readdress_readiness(readiness: dict[str, object]) -> dict[str, object]:
    core = {key: value for key, value in readiness.items() if key != "readiness_sha256"}
    return {**core, "readiness_sha256": _canonical_sha256(core)}


def _readdress_extension(record: dict[str, object]) -> dict[str, object]:
    core = {key: value for key, value in record.items() if key != "extension_sha256"}
    return {**core, "extension_sha256": _canonical_sha256(core)}


def _current_readiness() -> dict[str, object]:
    response = TestClient(app).get("/api/v2/system/startup-mvp-readiness")
    assert response.status_code == 200
    return response.json()


def _report(current: dict[str, object], *, system: str | None = None) -> dict[str, object]:
    historical = deepcopy(current)
    if system is not None:
        historical["environment"]["system"] = system
        historical = _readdress_readiness(historical)
    return compare_startup_readiness_evidence_to_current(build_startup_readiness_evidence(historical), current)


def _paths() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    current = _current_readiness()
    coherent = _report(current)
    drift_a = _report(current, system="historical-system-a")
    drift_b = _report(current, system="historical-system-b")

    first = build_startup_readiness_coherence_transition(coherent, drift_a)
    second = build_startup_readiness_coherence_transition(drift_a, drift_b)
    third = build_startup_readiness_coherence_transition(drift_b, coherent)
    divergent_second = build_startup_readiness_coherence_transition(drift_a, coherent)

    base = build_startup_readiness_coherence_path([first, second])
    extended = build_startup_readiness_coherence_path([first, second, third])
    divergent = build_startup_readiness_coherence_path([first, divergent_second])
    return base, extended, divergent


def test_path_extension_replays_deterministically_for_exact_prefix_extension() -> None:
    base, extended, _ = _paths()
    first = build_startup_readiness_coherence_path_extension(base, extended)
    second = build_startup_readiness_coherence_path_extension(base, extended)

    assert first == second
    assert first["contains_base_prefix"] is True
    assert first["is_strict_extension"] is True
    assert first["relation"] == "STRICT_PREFIX_EXTENSION"
    assert first["extension_transition_count"] == 1
    assert first["extension_transition_sha256s"] == [extended["transition_sha256s"][-1]]
    assert first["base_path_sha256"] == base["path_sha256"]
    assert first["candidate_path_sha256"] == extended["path_sha256"]
    assert first["extension_sha256"] == _canonical_sha256({key: value for key, value in first.items() if key != "extension_sha256"})
    assert verify_startup_readiness_coherence_path_extension(first) == first


def test_path_extension_classifies_identical_paths_without_claiming_extension() -> None:
    base, _, _ = _paths()
    record = build_startup_readiness_coherence_path_extension(base, base)

    assert record["contains_base_prefix"] is True
    assert record["is_strict_extension"] is False
    assert record["extension_transition_count"] == 0
    assert record["extension_transition_sha256s"] == []
    assert record["relation"] == "IDENTICAL"


def test_path_extension_reports_divergence_without_assigning_history_authority() -> None:
    base, _, divergent = _paths()
    record = build_startup_readiness_coherence_path_extension(base, divergent)

    assert record["contains_base_prefix"] is False
    assert record["is_strict_extension"] is False
    assert record["extension_transition_count"] == 0
    assert record["extension_transition_sha256s"] == []
    assert record["relation"] == "NOT_PREFIX_EXTENSION"
    assert record["authority"]["production_deployment_authorized"] is False
    assert record["authority"]["automatic_control_allowed"] is False
    assert record["authority"]["activation_allowed"] is False


def test_path_extension_rejects_nested_path_tampering() -> None:
    base, extended, _ = _paths()
    record = build_startup_readiness_coherence_path_extension(base, extended)
    forged = deepcopy(record)
    forged["candidate_path"]["path_sha256"] = "0" * 64
    forged = _readdress_extension(forged)

    with pytest.raises(ValueError, match="path digest does not match"):
        verify_startup_readiness_coherence_path_extension(forged)


def test_path_extension_rejects_readdressed_summary_forgery() -> None:
    base, extended, _ = _paths()
    record = build_startup_readiness_coherence_path_extension(base, extended)
    forged = deepcopy(record)
    forged["extension_transition_count"] = 0
    forged = _readdress_extension(forged)

    with pytest.raises(ValueError, match="extension_transition_count is inconsistent"):
        verify_startup_readiness_coherence_path_extension(forged)


def test_path_extension_rejects_readdressed_authority_escalation() -> None:
    base, extended, _ = _paths()
    record = build_startup_readiness_coherence_path_extension(base, extended)
    forged = deepcopy(record)
    forged["authority"]["automatic_control_allowed"] = True
    forged = _readdress_extension(forged)

    with pytest.raises(ValueError, match="cannot carry activation authority"):
        verify_startup_readiness_coherence_path_extension(forged)
