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
from app.startup_readiness_path_extension_chain_evidence import build_startup_readiness_coherence_path_extension_chain
from app.startup_readiness_path_extension_chain_extension_evidence import (
    build_startup_readiness_coherence_path_extension_chain_extension,
)
from app.startup_readiness_path_extension_chain_comparison_chain_evidence import (
    build_startup_readiness_coherence_path_extension_chain_comparison_chain,
)
from app.startup_readiness_path_extension_chain_comparison_chain_extension_evidence import (
    build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension,
    verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension,
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


def _comparison_chains() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    response = TestClient(app).get("/api/v2/system/startup-mvp-readiness")
    assert response.status_code == 200
    current = response.json()
    reports = [
        _report(current),
        _report(current, "hist-a"),
        _report(current, "hist-b"),
        _report(current, "hist-c"),
        _report(current, "hist-d"),
    ]
    transitions = [
        build_startup_readiness_coherence_transition(reports[index], reports[index + 1])
        for index in range(4)
    ]
    path2 = build_startup_readiness_coherence_path(transitions[:2])
    path3 = build_startup_readiness_coherence_path(transitions[:3])
    path4 = build_startup_readiness_coherence_path(transitions[:4])

    ext_22 = build_startup_readiness_coherence_path_extension(path2, path2)
    ext_23 = build_startup_readiness_coherence_path_extension(path2, path3)
    ext_33 = build_startup_readiness_coherence_path_extension(path3, path3)
    ext_34 = build_startup_readiness_coherence_path_extension(path3, path4)

    chain2 = build_startup_readiness_coherence_path_extension_chain([ext_22, ext_23])
    chain3 = build_startup_readiness_coherence_path_extension_chain([ext_22, ext_23, ext_33])
    chain4 = build_startup_readiness_coherence_path_extension_chain([ext_22, ext_23, ext_33, ext_34])

    comparison_23 = build_startup_readiness_coherence_path_extension_chain_extension(chain2, chain3)
    comparison_34 = build_startup_readiness_coherence_path_extension_chain_extension(chain3, chain4)
    comparison_44 = build_startup_readiness_coherence_path_extension_chain_extension(chain4, chain4)

    base = build_startup_readiness_coherence_path_extension_chain_comparison_chain(
        [comparison_23, comparison_34]
    )
    extended = build_startup_readiness_coherence_path_extension_chain_comparison_chain(
        [comparison_23, comparison_34, comparison_44]
    )
    divergent = build_startup_readiness_coherence_path_extension_chain_comparison_chain(
        [comparison_34, comparison_44]
    )
    return base, extended, divergent


def test_comparison_chain_extension_replays_deterministically_and_reports_strict_prefix() -> None:
    base, extended, _ = _comparison_chains()
    first = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension(base, extended)
    second = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension(base, extended)

    assert first == second
    assert first["relation"] == "STRICT_PREFIX_EXTENSION"
    assert first["contains_base_prefix"] is True
    assert first["is_strict_extension"] is True
    assert first["base_comparison_count"] == 2
    assert first["candidate_comparison_count"] == 3
    assert first["extension_comparison_count"] == 1
    assert first["extension_comparison_sha256s"] == [extended["comparison_sha256s"][-1]]
    assert verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension(first) == first


def test_comparison_chain_extension_distinguishes_identical_and_non_prefix() -> None:
    base, _, divergent = _comparison_chains()

    identical = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension(base, base)
    assert identical["relation"] == "IDENTICAL"
    assert identical["contains_base_prefix"] is True
    assert identical["is_strict_extension"] is False
    assert identical["extension_comparison_count"] == 0
    assert identical["extension_comparison_sha256s"] == []

    non_prefix = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension(base, divergent)
    assert non_prefix["relation"] == "NOT_PREFIX_EXTENSION"
    assert non_prefix["contains_base_prefix"] is False
    assert non_prefix["is_strict_extension"] is False
    assert non_prefix["extension_comparison_count"] == 0
    assert non_prefix["extension_comparison_sha256s"] == []


def test_comparison_chain_extension_rejects_nested_tampering_and_semantic_forgery() -> None:
    base, extended, _ = _comparison_chains()
    record = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension(base, extended)

    tampered = deepcopy(record)
    tampered["base_comparison_chain"]["comparisons"][0]["comparison_sha256"] = "0" * 64
    tampered = _readdress_comparison(tampered)
    with pytest.raises(ValueError, match="comparison digest does not match"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension(tampered)

    forged = deepcopy(record)
    forged["relation"] = "IDENTICAL"
    forged = _readdress_comparison(forged)
    with pytest.raises(ValueError, match="relation is inconsistent"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension(forged)


def test_comparison_chain_extension_rejects_authority_escalation() -> None:
    base, extended, _ = _comparison_chains()
    record = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension(base, extended)
    forged = deepcopy(record)
    forged["authority"]["automatic_control_allowed"] = True
    forged = _readdress_comparison(forged)
    with pytest.raises(ValueError, match="cannot carry activation authority"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension(forged)
