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
    verify_startup_readiness_coherence_path_extension_chain_comparison_chain,
)


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _readdress_readiness(readiness: dict[str, object]) -> dict[str, object]:
    core = {key: value for key, value in readiness.items() if key != "readiness_sha256"}
    return {**core, "readiness_sha256": _canonical_sha256(core)}


def _readdress_chain(record: dict[str, object]) -> dict[str, object]:
    core = {key: value for key, value in record.items() if key != "comparison_chain_sha256"}
    return {**core, "comparison_chain_sha256": _canonical_sha256(core)}


def _report(current: dict[str, object], system: str | None = None) -> dict[str, object]:
    historical = deepcopy(current)
    if system is not None:
        historical["environment"]["system"] = system
        historical = _readdress_readiness(historical)
    return compare_startup_readiness_evidence_to_current(build_startup_readiness_evidence(historical), current)


def _comparison_records() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
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
    return comparison_23, comparison_34, comparison_44


def test_comparison_chain_replays_deterministically_and_summarizes_relations() -> None:
    first_comparison, second_comparison, identical = _comparison_records()
    first = build_startup_readiness_coherence_path_extension_chain_comparison_chain(
        [first_comparison, second_comparison, identical]
    )
    second = build_startup_readiness_coherence_path_extension_chain_comparison_chain(
        [first_comparison, second_comparison, identical]
    )

    assert first == second
    assert first["comparison_count"] == 3
    assert first["relation_counts"] == {
        "IDENTICAL": 1,
        "STRICT_PREFIX_EXTENSION": 2,
        "NOT_PREFIX_EXTENSION": 0,
    }
    assert first["strict_extension_record_count"] == 2
    assert first["start_chain_sha256"] == first_comparison["base_chain_sha256"]
    assert first["end_chain_sha256"] == identical["candidate_chain_sha256"]
    assert verify_startup_readiness_coherence_path_extension_chain_comparison_chain(first) == first


def test_comparison_chain_rejects_insufficient_duplicate_and_broken_adjacency() -> None:
    first_comparison, second_comparison, identical = _comparison_records()

    with pytest.raises(ValueError, match="at least two records"):
        build_startup_readiness_coherence_path_extension_chain_comparison_chain([first_comparison])
    with pytest.raises(ValueError, match="duplicate comparison identities"):
        build_startup_readiness_coherence_path_extension_chain_comparison_chain(
            [first_comparison, first_comparison]
        )
    with pytest.raises(ValueError, match="adjacency is broken"):
        build_startup_readiness_coherence_path_extension_chain_comparison_chain(
            [first_comparison, identical]
        )

    valid = build_startup_readiness_coherence_path_extension_chain_comparison_chain(
        [first_comparison, second_comparison]
    )
    assert valid["comparison_count"] == 2


def test_comparison_chain_rejects_nested_tampering_and_summary_forgery() -> None:
    first_comparison, second_comparison, _ = _comparison_records()
    record = build_startup_readiness_coherence_path_extension_chain_comparison_chain(
        [first_comparison, second_comparison]
    )

    tampered = deepcopy(record)
    tampered["comparisons"][1]["comparison_sha256"] = "0" * 64
    tampered = _readdress_chain(tampered)
    with pytest.raises(ValueError, match="comparison digest does not match"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain(tampered)

    forged = deepcopy(record)
    forged["strict_extension_record_count"] = 999
    forged = _readdress_chain(forged)
    with pytest.raises(ValueError, match="strict_extension_record_count is inconsistent"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain(forged)


def test_comparison_chain_rejects_authority_escalation() -> None:
    first_comparison, second_comparison, _ = _comparison_records()
    record = build_startup_readiness_coherence_path_extension_chain_comparison_chain(
        [first_comparison, second_comparison]
    )
    forged = deepcopy(record)
    forged["authority"]["automatic_control_allowed"] = True
    forged = _readdress_chain(forged)
    with pytest.raises(ValueError, match="cannot carry activation authority"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain(forged)
