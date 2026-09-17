from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e163_e162_sequence_prefix_evidence as e163


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _sequence(label: str, ids: list[str]) -> dict[str, object]:
    return {"sequence_sha256": _digest(label), "comparison_sha256s": [_digest(value) for value in ids]}


@pytest.fixture(autouse=True)
def isolate_e162_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E162 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e163, "verify_startup_readiness_e162_e161_comparison_sequence", verify)


def test_e163_builds_replays_and_classifies_relations_deterministically() -> None:
    base = _sequence("base", ["c1", "c2"])
    identical = deepcopy(base)
    strict = _sequence("strict", ["c1", "c2", "c3", "c4"])
    divergent = _sequence("divergent", ["c1", "other"])
    same = e163.build_startup_readiness_e163_e162_sequence_prefix_comparison(base, identical)
    assert same["relation"] == "IDENTICAL"
    assert same["extension_comparison_sha256s"] == []
    assert same["extension_comparison_count"] == 0
    extended = e163.build_startup_readiness_e163_e162_sequence_prefix_comparison(base, strict)
    assert extended["relation"] == "STRICT_PREFIX_EXTENSION"
    assert extended["extension_comparison_sha256s"] == [_digest("c3"), _digest("c4")]
    assert extended["extension_comparison_count"] == 2
    assert e163.verify_startup_readiness_e163_e162_sequence_prefix_comparison(extended) == extended
    not_prefix = e163.build_startup_readiness_e163_e162_sequence_prefix_comparison(base, divergent)
    assert not_prefix["relation"] == "NOT_PREFIX_EXTENSION"
    assert not_prefix["extension_comparison_sha256s"] == []


def test_e163_rejects_nested_malformed_and_duplicate_identities() -> None:
    base = _sequence("base", ["c1", "c2"])
    with pytest.raises(ValueError, match="nested E162 rejected"):
        e163.build_startup_readiness_e163_e162_sequence_prefix_comparison(base, {"reject": True})
    malformed_sequence = _sequence("bad", ["c1", "c2"]); malformed_sequence["sequence_sha256"] = "bad"
    with pytest.raises(ValueError, match="valid E162 sequence identities"):
        e163.build_startup_readiness_e163_e162_sequence_prefix_comparison(base, malformed_sequence)
    malformed_comparison = _sequence("bad-comparison", ["c1", "c2"]); malformed_comparison["comparison_sha256s"][1] = "bad"
    with pytest.raises(ValueError, match="valid ordered E161"):
        e163.build_startup_readiness_e163_e162_sequence_prefix_comparison(base, malformed_comparison)
    duplicate = _sequence("duplicate", ["c1", "c1"])
    with pytest.raises(ValueError, match="unique ordered E161"):
        e163.build_startup_readiness_e163_e162_sequence_prefix_comparison(base, duplicate)


def test_e163_rejects_semantic_boundary_authority_embedded_and_digest_tampering() -> None:
    original = e163.build_startup_readiness_e163_e162_sequence_prefix_comparison(
        _sequence("base", ["c1", "c2"]), _sequence("candidate", ["c1", "c2", "c3"])
    )
    mutations = []
    relation = deepcopy(original); relation["relation"] = "IDENTICAL"; mutations.append(relation)
    suffix = deepcopy(original); suffix["extension_comparison_sha256s"] = []; mutations.append(suffix)
    count = deepcopy(original); count["extension_comparison_count"] = 99; mutations.append(count)
    no_boundary = deepcopy(original); no_boundary["truth_boundaries"] = []; mutations.append(no_boundary)
    authority = deepcopy(original); authority["authority"]["activation_allowed"] = True; mutations.append(authority)
    embedded = deepcopy(original); embedded["candidate_sequence"]["comparison_sha256s"][2] = _digest("other"); mutations.append(embedded)
    digest = deepcopy(original); digest["comparison_sha256"] = "0" * 64; mutations.append(digest)
    for record in mutations:
        with pytest.raises(ValueError):
            e163.verify_startup_readiness_e163_e162_sequence_prefix_comparison(record)
