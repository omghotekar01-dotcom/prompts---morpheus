from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest

import app.startup_readiness_e141_e140_sequence_prefix_evidence as e141


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _sequence(label: str, ids: list[str]) -> dict[str, object]:
    return {
        e141.E140_DIGEST_FIELD: _digest(label),
        "comparison_sha256s": [_digest(item) for item in ids],
    }


def _readdress(record: dict[str, object]) -> dict[str, object]:
    core = {key: value for key, value in record.items() if key != "comparison_sha256"}
    return {**core, "comparison_sha256": _canonical_sha256(core)}


@pytest.fixture
def e140_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def _verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict):
            raise ValueError("synthetic E140 contract requires a mapping")
        payload = deepcopy(record)
        if payload.get("__reject_nested__") is True:
            raise ValueError("synthetic nested E140 verification failure")
        digest = payload.get(e141.E140_DIGEST_FIELD)
        identities = payload.get("comparison_sha256s")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("synthetic E140 contract contains malformed sequence identity")
        if not isinstance(identities, list) or len(identities) < 2 or not all(isinstance(value, str) and len(value) == 64 for value in identities):
            raise ValueError("synthetic E140 contract contains malformed comparison identities")
        return payload

    monkeypatch.setattr(e141, "verify_startup_readiness_e140_e139_comparison_sequence", _verify)


def test_e141_identical_and_strict_prefix_replay_deterministically(e140_contract: None) -> None:
    base = _sequence("base", ["a", "b"])
    identical_candidate = _sequence("same-shape", ["a", "b"])
    identical = e141.build_startup_readiness_e141_e140_sequence_prefix_comparison(base, identical_candidate)
    assert identical["relation"] == "IDENTICAL"
    assert identical["extension_comparison_count"] == 0
    assert identical["extension_comparison_sha256s"] == []
    assert e141.verify_startup_readiness_e141_e140_sequence_prefix_comparison(identical) == identical

    candidate = _sequence("candidate", ["a", "b", "c", "d"])
    first = e141.build_startup_readiness_e141_e140_sequence_prefix_comparison(base, candidate)
    second = e141.build_startup_readiness_e141_e140_sequence_prefix_comparison(base, candidate)
    assert first == second
    assert first["relation"] == "STRICT_PREFIX_EXTENSION"
    assert first["contains_base_prefix"] is True
    assert first["is_strict_extension"] is True
    assert first["extension_comparison_count"] == 2
    assert first["extension_comparison_sha256s"] == [_digest("c"), _digest("d")]
    assert e141.verify_startup_readiness_e141_e140_sequence_prefix_comparison(first) == first


def test_e141_non_prefix_and_reverse_prefix_do_not_expose_suffix(e140_contract: None) -> None:
    base = _sequence("base", ["a", "b", "c"])
    divergent = _sequence("divergent", ["a", "x", "c", "d"])
    record = e141.build_startup_readiness_e141_e140_sequence_prefix_comparison(base, divergent)
    assert record["relation"] == "NOT_PREFIX_EXTENSION"
    assert record["contains_base_prefix"] is False
    assert record["extension_comparison_sha256s"] == []

    shorter = _sequence("shorter", ["a", "b"])
    reverse = e141.build_startup_readiness_e141_e140_sequence_prefix_comparison(base, shorter)
    assert reverse["relation"] == "NOT_PREFIX_EXTENSION"
    assert reverse["extension_comparison_count"] == 0
    assert reverse["extension_comparison_sha256s"] == []


def test_e141_propagates_nested_rejection_and_rejects_semantic_forgery(e140_contract: None) -> None:
    base = _sequence("base", ["a", "b"])
    candidate = _sequence("candidate", ["a", "b", "c"])
    record = e141.build_startup_readiness_e141_e140_sequence_prefix_comparison(base, candidate)

    nested = deepcopy(record)
    nested["candidate_e140_sequence"]["__reject_nested__"] = True
    nested = _readdress(nested)
    with pytest.raises(ValueError, match="synthetic nested E140 verification failure"):
        e141.verify_startup_readiness_e141_e140_sequence_prefix_comparison(nested)

    forged = deepcopy(record)
    forged["relation"] = "IDENTICAL"
    forged = _readdress(forged)
    with pytest.raises(ValueError, match="relation is inconsistent"):
        e141.verify_startup_readiness_e141_e140_sequence_prefix_comparison(forged)


def test_e141_rejects_malformed_suffix_truth_boundary_and_authority(e140_contract: None) -> None:
    record = e141.build_startup_readiness_e141_e140_sequence_prefix_comparison(
        _sequence("base", ["a", "b"]),
        _sequence("candidate", ["a", "b", "c"]),
    )

    malformed = deepcopy(record)
    malformed["extension_comparison_sha256s"] = ["not-a-digest"]
    malformed = _readdress(malformed)
    with pytest.raises(ValueError, match="extension_comparison_sha256s is inconsistent"):
        e141.verify_startup_readiness_e141_e140_sequence_prefix_comparison(malformed)

    missing = deepcopy(record)
    missing["truth_boundaries"] = []
    missing = _readdress(missing)
    with pytest.raises(ValueError, match="truth boundaries are missing"):
        e141.verify_startup_readiness_e141_e140_sequence_prefix_comparison(missing)

    authority = deepcopy(record)
    authority["authority"]["automatic_control_allowed"] = True
    authority = _readdress(authority)
    with pytest.raises(ValueError, match="cannot carry activation authority"):
        e141.verify_startup_readiness_e141_e140_sequence_prefix_comparison(authority)
