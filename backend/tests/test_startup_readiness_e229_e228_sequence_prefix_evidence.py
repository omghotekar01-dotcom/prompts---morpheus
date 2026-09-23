from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e229_e228_sequence_prefix_evidence as e229


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _sequence(label: str, ids: list[str]) -> dict[str, object]:
    return {
        "sequence_sha256": _digest(label),
        "comparison_sha256s": [_digest(value) for value in ids],
    }


@pytest.fixture(autouse=True)
def isolate_e228_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E228 rejected")
        return deepcopy(record)

    monkeypatch.setattr(
        e229,
        "verify_startup_readiness_e228_e227_comparison_sequence",
        verify,
    )


def test_e229_classifies_identical_strict_prefix_and_non_prefix() -> None:
    base = _sequence("s1", ["c1", "c2"])
    identical = _sequence("s2", ["c1", "c2"])
    extended = _sequence("s3", ["c1", "c2", "c3"])
    divergent = _sequence("s4", ["c1", "other"])

    same = e229.build_startup_readiness_e229_e228_sequence_prefix_comparison(base, identical)
    assert same["relation"] == "IDENTICAL"
    assert same["extension_comparison_sha256s"] == []
    assert same["extension_comparison_count"] == 0

    strict = e229.build_startup_readiness_e229_e228_sequence_prefix_comparison(base, extended)
    assert strict["relation"] == "STRICT_PREFIX_EXTENSION"
    assert strict["extension_comparison_sha256s"] == [_digest("c3")]
    assert strict["extension_comparison_count"] == 1

    other = e229.build_startup_readiness_e229_e228_sequence_prefix_comparison(base, divergent)
    assert other["relation"] == "NOT_PREFIX_EXTENSION"
    assert other["extension_comparison_sha256s"] == []
    assert other["extension_comparison_count"] == 0
    assert e229.verify_startup_readiness_e229_e228_sequence_prefix_comparison(strict) == strict


def test_e229_rejects_nested_malformed_and_duplicate_identities() -> None:
    base = _sequence("s1", ["c1", "c2"])
    with pytest.raises(ValueError, match="nested E228 rejected"):
        e229.build_startup_readiness_e229_e228_sequence_prefix_comparison(base, {"reject": True})

    malformed_sequence = _sequence("s2", ["c1", "c2"])
    malformed_sequence["sequence_sha256"] = "bad"
    with pytest.raises(ValueError, match="valid E228"):
        e229.build_startup_readiness_e229_e228_sequence_prefix_comparison(base, malformed_sequence)

    malformed_ordered = _sequence("s2", ["c1", "c2"])
    malformed_ordered["comparison_sha256s"] = ["bad", _digest("c2")]
    with pytest.raises(ValueError, match="valid ordered E227"):
        e229.build_startup_readiness_e229_e228_sequence_prefix_comparison(base, malformed_ordered)

    duplicate = _sequence("s2", ["c1", "c1"])
    with pytest.raises(ValueError, match="unique ordered E227"):
        e229.build_startup_readiness_e229_e228_sequence_prefix_comparison(base, duplicate)


def test_e229_rejects_relation_suffix_count_boundary_authority_embedded_and_digest_tampering() -> None:
    base = _sequence("s1", ["c1", "c2"])
    candidate = _sequence("s2", ["c1", "c2", "c3"])
    original = e229.build_startup_readiness_e229_e228_sequence_prefix_comparison(base, candidate)

    mutations = []
    relation = deepcopy(original); relation["relation"] = "IDENTICAL"; mutations.append(relation)
    suffix = deepcopy(original); suffix["extension_comparison_sha256s"] = []; mutations.append(suffix)
    count = deepcopy(original); count["extension_comparison_count"] = 9; mutations.append(count)
    boundary = deepcopy(original); boundary["truth_boundaries"] = []; mutations.append(boundary)
    authority = deepcopy(original); authority["authority"]["activation_allowed"] = True; mutations.append(authority)
    embedded = deepcopy(original); embedded["candidate_sequence"]["comparison_sha256s"][-1] = _digest("other"); mutations.append(embedded)
    digest = deepcopy(original); digest["comparison_sha256"] = "0" * 64; mutations.append(digest)

    for record in mutations:
        with pytest.raises(ValueError):
            e229.verify_startup_readiness_e229_e228_sequence_prefix_comparison(record)
