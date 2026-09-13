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
)
from app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_evidence import (
    build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain,
    verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain,
)


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _readdress_readiness(readiness: dict[str, object]) -> dict[str, object]:
    core = {key: value for key, value in readiness.items() if key != "readiness_sha256"}
    return {**core, "readiness_sha256": _canonical_sha256(core)}


def _readdress_chain(record: dict[str, object]) -> dict[str, object]:
    core = {key: value for key, value in record.items() if key != "comparison_extension_chain_sha256"}
    return {**core, "comparison_extension_chain_sha256": _canonical_sha256(core)}


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
    reports = [_report(current), _report(current, "hist-a"), _report(current, "hist-b"), _report(current, "hist-c")]
    transitions = [
        build_startup_readiness_coherence_transition(reports[index], reports[index + 1])
        for index in range(3)
    ]
    path2 = build_startup_readiness_coherence_path(transitions[:2])
    path3 = build_startup_readiness_coherence_path(transitions[:3])

    ext_22 = build_startup_readiness_coherence_path_extension(path2, path2)
    ext_23 = build_startup_readiness_coherence_path_extension(path2, path3)
    ext_33 = build_startup_readiness_coherence_path_extension(path3, path3)

    extension_chain2 = build_startup_readiness_coherence_path_extension_chain([ext_22, ext_23])
    extension_chain3 = build_startup_readiness_coherence_path_extension_chain([ext_22, ext_23, ext_33])

    prefix_22 = build_startup_readiness_coherence_path_extension_chain_extension(extension_chain2, extension_chain2)
    prefix_23 = build_startup_readiness_coherence_path_extension_chain_extension(extension_chain2, extension_chain3)
    prefix_33 = build_startup_readiness_coherence_path_extension_chain_extension(extension_chain3, extension_chain3)

    comparison_chain2 = build_startup_readiness_coherence_path_extension_chain_comparison_chain([prefix_22, prefix_23])
    comparison_chain3 = build_startup_readiness_coherence_path_extension_chain_comparison_chain([prefix_22, prefix_23, prefix_33])

    strict = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension(
        comparison_chain2, comparison_chain3
    )
    identical = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension(
        comparison_chain3, comparison_chain3
    )
    reverse = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension(
        comparison_chain3, comparison_chain2
    )
    return strict, identical, reverse


def test_comparison_extension_chain_replays_deterministically_and_summarizes_relations() -> None:
    strict, identical, _ = _comparison_records()
    first = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain([strict, identical])
    second = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain([strict, identical])

    assert first == second
    assert first["comparison_count"] == 2
    assert first["relation_counts"] == {
        "IDENTICAL": 1,
        "STRICT_PREFIX_EXTENSION": 1,
        "NOT_PREFIX_EXTENSION": 0,
    }
    assert first["strict_prefix_suffix_comparison_count"] == strict["extension_comparison_count"]
    assert first["start_comparison_chain_sha256"] == strict["base_comparison_chain_sha256"]
    assert first["end_comparison_chain_sha256"] == identical["candidate_comparison_chain_sha256"]
    assert verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain(first) == first


def test_comparison_extension_chain_rejects_minimum_duplicate_and_broken_adjacency() -> None:
    strict, identical, _ = _comparison_records()
    with pytest.raises(ValueError, match="at least two"):
        build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain([strict])
    with pytest.raises(ValueError, match="duplicate comparison identities"):
        build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain([strict, strict])
    # identical ends at comparison_chain3 while strict starts at comparison_chain2, so this ordering is non-adjacent.
    with pytest.raises(ValueError, match="broken structural adjacency"):
        build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain([identical, strict])


def test_comparison_extension_chain_rejects_nested_tampering_and_summary_forgery() -> None:
    strict, identical, _ = _comparison_records()
    record = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain([strict, identical])

    tampered = deepcopy(record)
    tampered["comparisons"][0]["comparison_sha256"] = "0" * 64
    tampered = _readdress_chain(tampered)
    with pytest.raises(ValueError, match="comparison-chain extension digest does not match"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain(tampered)

    forged = deepcopy(record)
    forged["relation_counts"]["IDENTICAL"] = 0
    forged["relation_counts"]["STRICT_PREFIX_EXTENSION"] = 2
    forged = _readdress_chain(forged)
    with pytest.raises(ValueError, match="relation_counts is inconsistent"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain(forged)


def test_comparison_extension_chain_rejects_authority_escalation() -> None:
    strict, identical, _ = _comparison_records()
    record = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain([strict, identical])
    forged = deepcopy(record)
    forged["authority"]["production_deployment_authorized"] = True
    forged = _readdress_chain(forged)
    with pytest.raises(ValueError, match="cannot carry activation authority"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain(forged)
