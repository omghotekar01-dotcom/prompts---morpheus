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
    verify_startup_readiness_coherence_path_extension_chain,
)


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _readdress_readiness(readiness: dict[str, object]) -> dict[str, object]:
    core = {key: value for key, value in readiness.items() if key != "readiness_sha256"}
    return {**core, "readiness_sha256": _canonical_sha256(core)}


def _readdress_chain(record: dict[str, object]) -> dict[str, object]:
    core = {key: value for key, value in record.items() if key != "chain_sha256"}
    return {**core, "chain_sha256": _canonical_sha256(core)}


def _report(current: dict[str, object], system: str | None = None) -> dict[str, object]:
    historical = deepcopy(current)
    if system is not None:
        historical["environment"]["system"] = system
        historical = _readdress_readiness(historical)
    return compare_startup_readiness_evidence_to_current(build_startup_readiness_evidence(historical), current)


def _extensions() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    response = TestClient(app).get("/api/v2/system/startup-mvp-readiness")
    assert response.status_code == 200
    current = response.json()
    reports = [_report(current), _report(current, "hist-a"), _report(current, "hist-b"), _report(current, "hist-c")]
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
    return identical, strict, tail_identical


def test_extension_chain_replays_deterministically_and_summarizes_structure() -> None:
    identical, strict, tail_identical = _extensions()
    first = build_startup_readiness_coherence_path_extension_chain([identical, strict, tail_identical])
    second = build_startup_readiness_coherence_path_extension_chain([identical, strict, tail_identical])

    assert first == second
    assert first["extension_count"] == 3
    assert first["relation_counts"] == {"IDENTICAL": 2, "STRICT_PREFIX_EXTENSION": 1, "NOT_PREFIX_EXTENSION": 0}
    assert first["strict_extension_transition_count"] == 1
    assert first["start_path_sha256"] == identical["base_path_sha256"]
    assert first["end_path_sha256"] == tail_identical["candidate_path_sha256"]
    assert verify_startup_readiness_coherence_path_extension_chain(first) == first


def test_extension_chain_requires_two_records_and_exact_adjacency() -> None:
    identical, strict, tail_identical = _extensions()
    with pytest.raises(ValueError, match="at least two"):
        build_startup_readiness_coherence_path_extension_chain([identical])
    with pytest.raises(ValueError, match="adjacency is broken"):
        build_startup_readiness_coherence_path_extension_chain([strict, identical])
    assert build_startup_readiness_coherence_path_extension_chain([strict, tail_identical])["extension_count"] == 2


def test_extension_chain_rejects_duplicate_identity_nested_tampering_and_summary_forgery() -> None:
    identical, strict, tail_identical = _extensions()
    with pytest.raises(ValueError, match="duplicate extension identities"):
        build_startup_readiness_coherence_path_extension_chain([identical, identical])

    chain = build_startup_readiness_coherence_path_extension_chain([identical, strict, tail_identical])
    tampered = deepcopy(chain)
    tampered["extensions"][1]["extension_sha256"] = "0" * 64
    tampered = _readdress_chain(tampered)
    with pytest.raises(ValueError, match="extension digest does not match"):
        verify_startup_readiness_coherence_path_extension_chain(tampered)

    forged = deepcopy(chain)
    forged["strict_extension_transition_count"] = 0
    forged = _readdress_chain(forged)
    with pytest.raises(ValueError, match="strict_extension_transition_count is inconsistent"):
        verify_startup_readiness_coherence_path_extension_chain(forged)


def test_extension_chain_rejects_authority_escalation() -> None:
    identical, strict, tail_identical = _extensions()
    chain = build_startup_readiness_coherence_path_extension_chain([identical, strict, tail_identical])
    forged = deepcopy(chain)
    forged["authority"]["automatic_control_allowed"] = True
    forged = _readdress_chain(forged)
    with pytest.raises(ValueError, match="cannot carry activation authority"):
        verify_startup_readiness_coherence_path_extension_chain(forged)
