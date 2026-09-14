from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest

import app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_evidence as e136_compare_module
from app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_evidence import (
    build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension,
    verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension,
)


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _chain(ids: list[str]) -> dict[str, object]:
    return {
        "comparison_sha256s": ids,
        "comparison_extension_chain_extension_chain_extension_chain_extension_chain_sha256": _digest("chain:" + ",".join(ids)),
    }


def _verify_e136_contract(record: object) -> dict[str, object]:
    if not isinstance(record, dict):
        raise ValueError("synthetic E136 chain must be a mapping")
    payload = deepcopy(record)
    if payload.get("_invalid_nested"):
        raise ValueError("synthetic E136 nested verification failed")
    ids = payload.get("comparison_sha256s")
    if not isinstance(ids, list) or not all(isinstance(value, str) and len(value) == 64 for value in ids):
        raise ValueError("synthetic E136 comparison identities are malformed")
    expected = _digest("chain:" + ",".join(ids))
    if payload.get("comparison_extension_chain_extension_chain_extension_chain_extension_chain_sha256") != expected:
        raise ValueError("synthetic E136 chain digest does not match")
    return payload


def _readdress_comparison(record: dict[str, object]) -> dict[str, object]:
    core = {key: value for key, value in record.items() if key != "comparison_sha256"}
    return {**core, "comparison_sha256": _canonical_sha256(core)}


@pytest.fixture(autouse=True)
def _isolate_e136_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        e136_compare_module,
        "verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain",
        _verify_e136_contract,
    )


def _chains() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    first = _digest("comparison:first")
    second = _digest("comparison:second")
    third = _digest("comparison:third")
    other = _digest("comparison:other")
    return _chain([first, second]), _chain([first, second, third]), _chain([other, third])


def test_e136_prefix_comparison_replays_deterministically() -> None:
    base, extended, _ = _chains()
    first = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
        base, extended
    )
    second = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
        base, extended
    )
    assert first == second
    assert first["relation"] == "STRICT_PREFIX_EXTENSION"
    assert first["contains_base_prefix"] is True
    assert first["is_strict_extension"] is True
    assert first["extension_comparison_count"] == 1
    assert first["extension_comparison_sha256s"] == [extended["comparison_sha256s"][-1]]
    assert verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
        first
    ) == first


def test_e136_prefix_comparison_classifies_identical_and_non_prefix() -> None:
    base, extended, divergent = _chains()
    identical = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
        base, base
    )
    assert identical["relation"] == "IDENTICAL"
    assert identical["extension_comparison_count"] == 0
    non_prefix = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
        base, divergent
    )
    assert non_prefix["relation"] == "NOT_PREFIX_EXTENSION"
    assert non_prefix["contains_base_prefix"] is False
    reverse = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
        extended, base
    )
    assert reverse["relation"] == "NOT_PREFIX_EXTENSION"


def test_e136_prefix_comparison_propagates_nested_failure_and_rejects_semantic_forgery() -> None:
    base, extended, _ = _chains()
    invalid = deepcopy(extended)
    invalid["_invalid_nested"] = True
    with pytest.raises(ValueError, match="synthetic E136 nested verification failed"):
        build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
            base, invalid
        )

    record = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
        base, extended
    )
    forged = deepcopy(record)
    forged["relation"] = "IDENTICAL"
    forged["is_strict_extension"] = False
    forged = _readdress_comparison(forged)
    with pytest.raises(ValueError, match="is inconsistent with embedded chains"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
            forged
        )


def test_e136_prefix_comparison_rejects_nested_digest_authority_boundaries_and_malformed_suffix() -> None:
    base, extended, _ = _chains()
    record = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
        base, extended
    )

    tampered = deepcopy(record)
    tampered["candidate_comparison_extension_chain_extension_chain_extension_chain_extension_chain"][
        "comparison_extension_chain_extension_chain_extension_chain_extension_chain_sha256"
    ] = "0" * 64
    tampered = _readdress_comparison(tampered)
    with pytest.raises(ValueError, match="synthetic E136 chain digest does not match"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
            tampered
        )

    authority = deepcopy(record)
    authority["authority"]["automatic_control_allowed"] = True
    authority = _readdress_comparison(authority)
    with pytest.raises(ValueError, match="cannot carry activation authority"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
            authority
        )

    missing = deepcopy(record)
    missing["truth_boundaries"] = []
    missing = _readdress_comparison(missing)
    with pytest.raises(ValueError, match="truth boundaries are missing"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
            missing
        )

    malformed = deepcopy(record)
    malformed["extension_comparison_sha256s"] = ["not-a-digest"]
    malformed = _readdress_comparison(malformed)
    with pytest.raises(ValueError, match="extension_comparison_sha256s is inconsistent with embedded chains"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
            malformed
        )
