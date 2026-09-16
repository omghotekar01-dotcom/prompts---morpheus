from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e161_e160_sequence_prefix_evidence as e161


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _sequence(label: str, ids: list[str]) -> dict[str, object]:
    return {
        "sequence_sha256": _digest(label),
        "comparison_sha256s": [_digest(value) for value in ids],
    }


@pytest.fixture(autouse=True)
def isolate_e160_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E160 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e161, "verify_startup_readiness_e160_e159_comparison_sequence", verify)


def test_e161_builds_and_replays_identical_deterministically() -> None:
    base = _sequence("s1", ["c1", "c2"])
    first = e161.build_startup_readiness_e161_e160_sequence_prefix_comparison(base, deepcopy(base))
    second = e161.build_startup_readiness_e161_e160_sequence_prefix_comparison(deepcopy(base), deepcopy(base))
    assert first == second
    assert first["relation"] == "IDENTICAL"
    assert first["extension_comparison_sha256s"] == []
    assert first["extension_comparison_count"] == 0
    assert e161.verify_startup_readiness_e161_e160_sequence_prefix_comparison(first) == first


def test_e161_classifies_strict_prefix_and_discloses_exact_suffix() -> None:
    base = _sequence("s1", ["c1", "c2"])
    candidate = _sequence("s2", ["c1", "c2", "c3", "c4"])
    record = e161.build_startup_readiness_e161_e160_sequence_prefix_comparison(base, candidate)
    assert record["relation"] == "STRICT_PREFIX_EXTENSION"
    assert record["extension_comparison_sha256s"] == [_digest("c3"), _digest("c4")]
    assert record["extension_comparison_count"] == 2


def test_e161_classifies_non_prefix_without_suffix_disclosure() -> None:
    record = e161.build_startup_readiness_e161_e160_sequence_prefix_comparison(
        _sequence("s1", ["c1", "c2"]), _sequence("s2", ["c1", "other", "c3"])
    )
    assert record["relation"] == "NOT_PREFIX_EXTENSION"
    assert record["extension_comparison_sha256s"] == []
    assert record["extension_comparison_count"] == 0


def test_e161_rejects_nested_malformed_and_duplicate_identities() -> None:
    valid = _sequence("s1", ["c1", "c2"])
    with pytest.raises(ValueError, match="nested E160 rejected"):
        e161.build_startup_readiness_e161_e160_sequence_prefix_comparison(valid, {"reject": True})
    malformed = _sequence("s2", ["c1", "c2"]); malformed["sequence_sha256"] = "bad"
    with pytest.raises(ValueError, match="valid E160 sequence identities"):
        e161.build_startup_readiness_e161_e160_sequence_prefix_comparison(valid, malformed)
    bad_ids = _sequence("s2", ["c1", "c2"]); bad_ids["comparison_sha256s"] = [_digest("c1"), "bad"]
    with pytest.raises(ValueError, match="valid ordered E159"):
        e161.build_startup_readiness_e161_e160_sequence_prefix_comparison(valid, bad_ids)
    duplicate = _sequence("s2", ["c1", "c1"])
    with pytest.raises(ValueError, match="unique ordered E159"):
        e161.build_startup_readiness_e161_e160_sequence_prefix_comparison(valid, duplicate)


def test_e161_rejects_semantic_boundary_authority_embedded_and_digest_tampering() -> None:
    original = e161.build_startup_readiness_e161_e160_sequence_prefix_comparison(
        _sequence("s1", ["c1", "c2"]), _sequence("s2", ["c1", "c2", "c3"])
    )
    mutations = []
    relation = deepcopy(original); relation["relation"] = "IDENTICAL"; mutations.append(relation)
    suffix = deepcopy(original); suffix["extension_comparison_sha256s"] = []; mutations.append(suffix)
    count = deepcopy(original); count["extension_comparison_count"] = 99; mutations.append(count)
    no_boundary = deepcopy(original); no_boundary["truth_boundaries"] = []; mutations.append(no_boundary)
    authority = deepcopy(original); authority["authority"]["activation_allowed"] = True; mutations.append(authority)
    embedded = deepcopy(original); embedded["candidate_sequence"]["comparison_sha256s"][-1] = _digest("other"); mutations.append(embedded)
    digest = deepcopy(original); digest["comparison_sha256"] = "0" * 64; mutations.append(digest)
    for record in mutations:
        with pytest.raises(ValueError):
            e161.verify_startup_readiness_e161_e160_sequence_prefix_comparison(record)
