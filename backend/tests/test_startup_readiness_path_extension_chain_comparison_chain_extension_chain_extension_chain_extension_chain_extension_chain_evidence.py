from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest

import app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_evidence as e135_chain_module
from app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_evidence import (
    build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain,
    verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain,
)


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _readdress_chain(record: dict[str, object]) -> dict[str, object]:
    core = {
        key: value
        for key, value in record.items()
        if key != "comparison_extension_chain_extension_chain_extension_chain_extension_chain_sha256"
    }
    return {**core, "comparison_extension_chain_extension_chain_extension_chain_extension_chain_sha256": _canonical_sha256(core)}


def _e135_record(label: str, relation: str, base: str, candidate: str, suffix_count: int = 0) -> dict[str, object]:
    return {
        "comparison_sha256": _digest(f"comparison:{label}:{relation}:{base}:{candidate}:{suffix_count}"),
        "relation": relation,
        "extension_comparison_count": suffix_count,
        "base_comparison_extension_chain_extension_chain_extension_chain_sha256": _digest(base),
        "candidate_comparison_extension_chain_extension_chain_extension_chain_sha256": _digest(candidate),
    }


def _verify_e135_contract(record: object) -> dict[str, object]:
    if not isinstance(record, dict):
        raise ValueError("synthetic E135 comparison must be a mapping")
    payload = deepcopy(record)
    if payload.get("_invalid_nested"):
        raise ValueError("synthetic E135 nested verification failed")
    required = {
        "comparison_sha256",
        "relation",
        "extension_comparison_count",
        "base_comparison_extension_chain_extension_chain_extension_chain_sha256",
        "candidate_comparison_extension_chain_extension_chain_extension_chain_sha256",
    }
    if not required.issubset(payload):
        raise ValueError("synthetic E135 comparison contract is incomplete")
    return payload


@pytest.fixture(autouse=True)
def _isolate_e135_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        e135_chain_module,
        "verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension",
        _verify_e135_contract,
    )


def _records() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    first = _e135_record("first", "STRICT_PREFIX_EXTENSION", "a", "b", 2)
    second = _e135_record("second", "IDENTICAL", "b", "b")
    third = _e135_record("third", "NOT_PREFIX_EXTENSION", "b", "c")
    return first, second, third


def test_e135_comparison_chain_replays_deterministically() -> None:
    first, second, third = _records()
    chain = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain(
        [first, second, third]
    )
    replay = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain(
        [first, second, third]
    )
    assert chain == replay
    assert chain["comparison_count"] == 3
    assert chain["comparison_sha256s"] == [first["comparison_sha256"], second["comparison_sha256"], third["comparison_sha256"]]
    assert chain["relation_counts"] == {"IDENTICAL": 1, "STRICT_PREFIX_EXTENSION": 1, "NOT_PREFIX_EXTENSION": 1}
    assert chain["strict_prefix_suffix_comparison_count"] == 2
    assert verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain(
        chain
    ) == chain


def test_e135_comparison_chain_rejects_minimum_duplicate_and_broken_adjacency() -> None:
    first, second, _ = _records()
    with pytest.raises(ValueError, match="at least two comparison records"):
        build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain([first])
    with pytest.raises(ValueError, match="duplicate comparison identities"):
        build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain([first, first])
    with pytest.raises(ValueError, match="broken structural adjacency"):
        build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain([second, first])


def test_e135_comparison_chain_propagates_nested_verifier_failure_and_rejects_summary_forgery() -> None:
    first, second, third = _records()
    invalid = deepcopy(second)
    invalid["_invalid_nested"] = True
    with pytest.raises(ValueError, match="synthetic E135 nested verification failed"):
        build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain(
            [first, invalid, third]
        )

    chain = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain(
        [first, second, third]
    )
    forged = deepcopy(chain)
    forged["relation_counts"]["IDENTICAL"] = 2
    forged["relation_counts"]["NOT_PREFIX_EXTENSION"] = 0
    forged = _readdress_chain(forged)
    with pytest.raises(ValueError, match="relation_counts is inconsistent with embedded comparisons"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain(forged)


def test_e135_comparison_chain_rejects_authority_boundaries_and_malformed_identity() -> None:
    first, second, third = _records()
    chain = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain(
        [first, second, third]
    )
    authority = deepcopy(chain)
    authority["authority"]["automatic_control_allowed"] = True
    authority = _readdress_chain(authority)
    with pytest.raises(ValueError, match="cannot carry activation authority"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain(authority)

    missing = deepcopy(chain)
    missing["truth_boundaries"] = []
    missing = _readdress_chain(missing)
    with pytest.raises(ValueError, match="truth boundaries are missing"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain(missing)

    malformed = deepcopy(chain)
    malformed["comparison_sha256s"][0] = "not-a-digest"
    malformed = _readdress_chain(malformed)
    with pytest.raises(ValueError, match="comparison_sha256s is inconsistent with embedded comparisons"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain(malformed)
