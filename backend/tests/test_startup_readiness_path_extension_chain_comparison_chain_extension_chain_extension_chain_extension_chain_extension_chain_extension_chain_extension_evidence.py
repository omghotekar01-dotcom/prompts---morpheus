from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from functools import lru_cache

import pytest
from fastapi.testclient import TestClient

from app.server import app
from app.startup_readiness_evidence import build_startup_readiness_coherence_transition, build_startup_readiness_evidence, compare_startup_readiness_evidence_to_current
from app.startup_readiness_path_evidence import build_startup_readiness_coherence_path
from app.startup_readiness_path_extension_evidence import build_startup_readiness_coherence_path_extension
from app.startup_readiness_path_extension_chain_evidence import build_startup_readiness_coherence_path_extension_chain
from app.startup_readiness_path_extension_chain_extension_evidence import build_startup_readiness_coherence_path_extension_chain_extension
from app.startup_readiness_path_extension_chain_comparison_chain_evidence import build_startup_readiness_coherence_path_extension_chain_comparison_chain
from app.startup_readiness_path_extension_chain_comparison_chain_extension_evidence import build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension
from app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_evidence import build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain
from app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_evidence import build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension
from app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_chain_evidence import build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain
from app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_evidence import build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension
from app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_evidence import build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain
from app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_evidence import build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension
from app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_evidence import build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain
from app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_evidence import build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension
from app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_evidence import build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain
from app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_evidence import (
    build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension,
    verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension,
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


@lru_cache(maxsize=1)
def _e138_chains() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    """Build the immutable E138 test graph once per worker instead of rebuilding its full nested proof tree per test."""

    current = TestClient(app).get("/api/v2/system/startup-mvp-readiness").json()
    reports = [_report(current), _report(current, "hist-a"), _report(current, "hist-b"), _report(current, "hist-c")]
    transitions = [build_startup_readiness_coherence_transition(reports[i], reports[i + 1]) for i in range(3)]
    path2 = build_startup_readiness_coherence_path(transitions[:2])
    path3 = build_startup_readiness_coherence_path(transitions[:3])
    ext22 = build_startup_readiness_coherence_path_extension(path2, path2)
    ext23 = build_startup_readiness_coherence_path_extension(path2, path3)
    ext33 = build_startup_readiness_coherence_path_extension(path3, path3)
    echain2 = build_startup_readiness_coherence_path_extension_chain([ext22, ext23])
    echain3 = build_startup_readiness_coherence_path_extension_chain([ext22, ext23, ext33])
    p22 = build_startup_readiness_coherence_path_extension_chain_extension(echain2, echain2)
    p23 = build_startup_readiness_coherence_path_extension_chain_extension(echain2, echain3)
    p33 = build_startup_readiness_coherence_path_extension_chain_extension(echain3, echain3)
    cchain2 = build_startup_readiness_coherence_path_extension_chain_comparison_chain([p22, p23])
    cchain3 = build_startup_readiness_coherence_path_extension_chain_comparison_chain([p22, p23, p33])
    strict = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension(cchain2, cchain3)
    identical = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension(cchain3, cchain3)
    reverse = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension(cchain3, cchain2)
    base = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain([strict, identical])
    extended = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain([strict, identical, reverse])
    first = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension(base, extended)
    second = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension(extended, extended)
    third = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension(extended, base)
    chain2 = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain([first, second])
    chain3 = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain([first, second, third])
    r1 = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension(chain2, chain3)
    r2 = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension(chain3, chain3)
    r3 = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension(chain3, chain2)
    base_chain = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain([r1, r2])
    extended_chain = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain([r1, r2, r3])
    e135_1 = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension(base_chain, extended_chain)
    e135_2 = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension(extended_chain, extended_chain)
    e135_3 = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension(extended_chain, base_chain)
    e136_base = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain([e135_1, e135_2])
    e136_extended = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain([e135_1, e135_2, e135_3])
    e137_1 = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(e136_base, e136_extended)
    e137_2 = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(e136_extended, e136_extended)
    e137_3 = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(e136_extended, e136_base)
    e138_base = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain([e137_1, e137_2])
    e138_extended = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain([e137_1, e137_2, e137_3])
    e138_divergent = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain([e137_2, e137_3])
    return e138_base, e138_extended, e138_divergent


@lru_cache(maxsize=1)
def _e139_records() -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    """Build each canonical E139 relation once; mutation tests operate only on deep copies."""

    base, extended, divergent = _e138_chains()
    strict = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(base, extended)
    identical = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(base, base)
    non_prefix = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(base, divergent)
    reverse = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(extended, base)
    return strict, identical, non_prefix, reverse


def test_e138_prefix_comparison_replays_deterministically() -> None:
    base, extended, _ = _e138_chains()
    strict, _, _, _ = _e139_records()
    replayed = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(base, extended)
    assert replayed == strict
    assert strict["relation"] == "STRICT_PREFIX_EXTENSION"
    assert strict["contains_base_prefix"] is True
    assert strict["is_strict_extension"] is True
    assert strict["extension_comparison_count"] == 1
    assert strict["extension_comparison_sha256s"] == [extended["comparison_sha256s"][-1]]
    assert strict["base_comparison_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_sha256"] == base[
        "comparison_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_sha256"
    ]
    assert strict["candidate_comparison_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_sha256"] == extended[
        "comparison_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_sha256"
    ]
    assert verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(strict) == strict


def test_e138_prefix_comparison_classifies_identical_and_non_prefix() -> None:
    _, identical, non_prefix, reverse = _e139_records()
    assert identical["relation"] == "IDENTICAL"
    assert identical["extension_comparison_count"] == 0
    assert non_prefix["relation"] == "NOT_PREFIX_EXTENSION"
    assert non_prefix["contains_base_prefix"] is False
    assert reverse["relation"] == "NOT_PREFIX_EXTENSION"


def test_e138_prefix_comparison_rejects_nested_tampering_and_semantic_forgery() -> None:
    record, _, _, _ = _e139_records()

    tampered = deepcopy(record)
    tampered["candidate_comparison_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain"][
        "comparison_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_sha256"
    ] = "0" * 64
    tampered = _readdress_comparison(tampered)
    with pytest.raises(ValueError, match="digest does not match canonical record"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(tampered)

    forged = deepcopy(record)
    forged["relation"] = "IDENTICAL"
    forged["is_strict_extension"] = False
    forged = _readdress_comparison(forged)
    with pytest.raises(ValueError, match="is inconsistent with embedded chains"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(forged)


def test_e138_prefix_comparison_rejects_authority_boundaries_and_malformed_suffix() -> None:
    record, _, _, _ = _e139_records()

    authority = deepcopy(record)
    authority["authority"]["automatic_control_allowed"] = True
    authority = _readdress_comparison(authority)
    with pytest.raises(ValueError, match="cannot carry activation authority"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(authority)

    missing = deepcopy(record)
    missing["truth_boundaries"] = []
    missing = _readdress_comparison(missing)
    with pytest.raises(ValueError, match="truth boundaries are missing"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(missing)

    malformed = deepcopy(record)
    malformed["extension_comparison_sha256s"] = ["not-a-digest"]
    malformed = _readdress_comparison(malformed)
    with pytest.raises(ValueError, match="extension_comparison_sha256s is inconsistent with embedded chains"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(malformed)
