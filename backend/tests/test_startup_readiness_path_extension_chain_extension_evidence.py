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
from app.startup_readiness_path_extension_evidence import build_startup_readiness_coherence_path_extension
from app.startup_readiness_path_extension_chain_evidence import (
    build_startup_readiness_coherence_path_extension_chain,
)
from app.startup_readiness_path_extension_chain_extension_evidence import (
    build_startup_readiness_coherence_path_extension_chain_extension,
    verify_startup_readiness_coherence_path_extension_chain_extension,
)


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _readdress_readiness(readiness: dict[str, object]) -> dict[str, object]:
    core = {key: value for key, value in readiness.items() if key != "readiness_sha256"}
    return {**core, "readiness_sha256": _canonical_sha256(core)}


def _readdress_comparison(record: dict[str, object]) -> dict[str, object]:
    core = {key: value for key, value in record.items() if key != "comparison_sha256"}
    return {**core, "comparison_sha256": _canonical_sha256(core)}


def _report(current: dict[str, object], system: str | None = None) -> dict[str, object]:
    historical = deepcopy(current)
    if system is not None:
        historical["environment"]["system"] = system
        historical = _readdress_readiness(historical)
    return compare_startup_readiness_evidence_to_current(build_startup_readiness_evidence(historical), current)


def _chains() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    response = TestClient(app).get("/api/v2/system/startup-mvp-readiness")
    assert response.status_code == 200
    current = response.json()
    reports = [
        _report(current),
        _report(current, "hist-a"),
        _report(current, "hist-b"),
        _report(current, "hist-c"),
    ]
    transitions = [
        build_startup_readiness_coherence_transition(reports[0], reports[1]),
        build_startup_readiness_coherence_transition(reports[1], reports[2]),
        build_startup_readiness_coherence_transition(reports[2], reports[3]),
    ]
    path2 = build_startup_readiness_coherence_path(transitions[:2])
    path3 = build_startup_readiness_coherence_path(transitions[:3])
    identical = build_startup_readiness_coherence_path_extension(path2, path2)
    strict = build_startup_readiness_coherence_path_extension(path2, path3)
    tail_identical = build_startup_readiness_coherence_path_extension(path3, path3)
    base = build_startup_readiness_coherence_path_extension_chain([identical, strict])
    extended = build_startup_readiness_coherence_path_extension_chain([identical, strict, tail_identical])
    divergent = build_startup_readiness_coherence_path_extension_chain([strict, tail_identical])
    return base, extended, divergent


def test_chain_extension_comparison_replays_deterministically_for_strict_prefix() -> None:
    base, extended, _ = _chains()
    first = build_startup_readiness_coherence_path_extension_chain_extension(base, extended)
    second = build_startup_readiness_coherence_path_extension_chain_extension(base, extended)

    assert first == second
    assert first["relation"] == "STRICT_PREFIX_EXTENSION"
    assert first["contains_base_prefix"] is True
    assert first["is_strict_extension"] is True
    assert first["base_extension_count"] == 2
    assert first["candidate_extension_count"] == 3
    assert first["extension_record_count"] == 1
    assert first["extension_sha256s"] == [extended["extension_sha256s"][2]]
    assert verify_startup_readiness_coherence_path_extension_chain_extension(first) == first


def test_chain_extension_comparison_distinguishes_identical_and_non_prefix() -> None:
    base, _, divergent = _chains()
    identical = build_startup_readiness_coherence_path_extension_chain_extension(base, base)
    non_prefix = build_startup_readiness_coherence_path_extension_chain_extension(base, divergent)

    assert identical["relation"] == "IDENTICAL"
    assert identical["extension_record_count"] == 0
    assert identical["extension_sha256s"] == []
    assert non_prefix["relation"] == "NOT_PREFIX_EXTENSION"
    assert non_prefix["contains_base_prefix"] is False
    assert non_prefix["is_strict_extension"] is False
    assert non_prefix["extension_record_count"] == 0
    assert non_prefix["extension_sha256s"] == []


def test_chain_extension_comparison_rejects_nested_tampering_and_semantic_forgery() -> None:
    base, extended, _ = _chains()
    record = build_startup_readiness_coherence_path_extension_chain_extension(base, extended)

    tampered = deepcopy(record)
    tampered["candidate_chain"]["chain_sha256"] = "0" * 64
    tampered = _readdress_comparison(tampered)
    with pytest.raises(ValueError, match="chain digest does not match"):
        verify_startup_readiness_coherence_path_extension_chain_extension(tampered)

    forged = deepcopy(record)
    forged["relation"] = "IDENTICAL"
    forged = _readdress_comparison(forged)
    with pytest.raises(ValueError, match="relation is inconsistent"):
        verify_startup_readiness_coherence_path_extension_chain_extension(forged)


def test_chain_extension_comparison_rejects_authority_escalation() -> None:
    base, extended, _ = _chains()
    record = build_startup_readiness_coherence_path_extension_chain_extension(base, extended)
    forged = deepcopy(record)
    forged["authority"]["production_deployment_authorized"] = True
    forged = _readdress_comparison(forged)
    with pytest.raises(ValueError, match="cannot carry activation authority"):
        verify_startup_readiness_coherence_path_extension_chain_extension(forged)
