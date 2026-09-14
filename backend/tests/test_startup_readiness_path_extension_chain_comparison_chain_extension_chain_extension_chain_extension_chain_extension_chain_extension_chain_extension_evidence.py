from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest

import app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_evidence as e139


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _readdress_comparison(record: dict[str, object]) -> dict[str, object]:
    core = {key: value for key, value in record.items() if key != "comparison_sha256"}
    return {**core, "comparison_sha256": _canonical_sha256(core)}


def _e138_chain(label: str, comparison_labels: list[str]) -> dict[str, object]:
    """Minimal E138 contract record for isolated E139 semantics tests.

    The E138 verifier itself is tested in its own suite. E139 tests patch that dependency
    with a fail-closed contract double so this layer does not reconstruct the complete
    E1-E138 proof graph for every backend compatibility lane.
    """

    return {
        "comparison_sha256s": [_digest(item) for item in comparison_labels],
        "comparison_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_sha256": _digest(label),
    }


@pytest.fixture
def e138_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def _verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict):
            raise ValueError("synthetic E138 contract requires a mapping")
        payload = deepcopy(record)
        if payload.get("__reject_nested__") is True:
            raise ValueError("synthetic nested E138 verification failure")
        ids = payload.get("comparison_sha256s")
        identity = payload.get("comparison_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_sha256")
        if not isinstance(ids, list) or not all(isinstance(value, str) and len(value) == 64 for value in ids):
            raise ValueError("synthetic E138 contract contains malformed comparison identities")
        if not isinstance(identity, str) or len(identity) != 64:
            raise ValueError("synthetic E138 contract contains malformed chain identity")
        return payload

    monkeypatch.setattr(
        e139,
        "verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain",
        _verify,
    )


def _chains() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    base = _e138_chain("base", ["a", "b"])
    extended = _e138_chain("extended", ["a", "b", "c"])
    divergent = _e138_chain("divergent", ["a", "d"])
    return base, extended, divergent


def test_e139_prefix_comparison_replays_deterministically(e138_contract: None) -> None:
    base, extended, _ = _chains()
    first = e139.build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
        base, extended
    )
    second = e139.build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
        base, extended
    )
    assert first == second
    assert first["relation"] == "STRICT_PREFIX_EXTENSION"
    assert first["contains_base_prefix"] is True
    assert first["is_strict_extension"] is True
    assert first["extension_comparison_count"] == 1
    assert first["extension_comparison_sha256s"] == [extended["comparison_sha256s"][-1]]
    assert first["base_comparison_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_sha256"] == base[
        "comparison_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_sha256"
    ]
    assert first["candidate_comparison_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_sha256"] == extended[
        "comparison_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_sha256"
    ]
    assert (
        e139.verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(first)
        == first
    )


def test_e139_prefix_comparison_classifies_identical_and_non_prefix(e138_contract: None) -> None:
    base, extended, divergent = _chains()
    identical = e139.build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
        base, base
    )
    assert identical["relation"] == "IDENTICAL"
    assert identical["extension_comparison_count"] == 0

    non_prefix = e139.build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
        base, divergent
    )
    assert non_prefix["relation"] == "NOT_PREFIX_EXTENSION"
    assert non_prefix["contains_base_prefix"] is False

    reverse = e139.build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
        extended, base
    )
    assert reverse["relation"] == "NOT_PREFIX_EXTENSION"


def test_e139_prefix_comparison_propagates_nested_verifier_failure_and_rejects_semantic_forgery(e138_contract: None) -> None:
    base, extended, _ = _chains()
    record = e139.build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
        base, extended
    )

    nested_rejected = deepcopy(record)
    nested_rejected["candidate_comparison_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain"]["__reject_nested__"] = True
    nested_rejected = _readdress_comparison(nested_rejected)
    with pytest.raises(ValueError, match="synthetic nested E138 verification failure"):
        e139.verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
            nested_rejected
        )

    forged = deepcopy(record)
    forged["relation"] = "IDENTICAL"
    forged["is_strict_extension"] = False
    forged = _readdress_comparison(forged)
    with pytest.raises(ValueError, match="is inconsistent with embedded chains"):
        e139.verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
            forged
        )


def test_e139_prefix_comparison_rejects_authority_boundaries_and_malformed_suffix(e138_contract: None) -> None:
    base, extended, _ = _chains()
    record = e139.build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
        base, extended
    )

    authority = deepcopy(record)
    authority["authority"]["automatic_control_allowed"] = True
    authority = _readdress_comparison(authority)
    with pytest.raises(ValueError, match="cannot carry activation authority"):
        e139.verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
            authority
        )

    missing = deepcopy(record)
    missing["truth_boundaries"] = []
    missing = _readdress_comparison(missing)
    with pytest.raises(ValueError, match="truth boundaries are missing"):
        e139.verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
            missing
        )

    malformed = deepcopy(record)
    malformed["extension_comparison_sha256s"] = ["not-a-digest"]
    malformed = _readdress_comparison(malformed)
    with pytest.raises(ValueError, match="extension_comparison_sha256s is inconsistent with embedded chains"):
        e139.verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
            malformed
        )
