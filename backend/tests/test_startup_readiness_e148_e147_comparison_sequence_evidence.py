from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e148_e147_comparison_sequence_evidence as e148


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _comparison(label: str, base: str, candidate: str, relation: str = "IDENTICAL", suffix_count: int = 0) -> dict[str, object]:
    return {
        "comparison_sha256": _digest(label),
        "base_e146_sequence_sha256": _digest(base),
        "candidate_e146_sequence_sha256": _digest(candidate),
        "relation": relation,
        "extension_comparison_count": suffix_count,
    }


@pytest.fixture(autouse=True)
def isolate_e147_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E147 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e148, "verify_startup_readiness_e147_e146_sequence_prefix_comparison", verify)


def test_e148_replays_deterministically_and_summarizes() -> None:
    comparisons = [
        _comparison("c1", "s1", "s2", "STRICT_PREFIX_EXTENSION", 2),
        _comparison("c2", "s2", "s3", "NOT_PREFIX_EXTENSION", 0),
        _comparison("c3", "s3", "s4", "IDENTICAL", 0),
    ]
    first = e148.build_startup_readiness_e148_e147_comparison_sequence(comparisons)
    second = e148.build_startup_readiness_e148_e147_comparison_sequence(deepcopy(comparisons))
    assert first == second
    assert first["comparison_count"] == 3
    assert first["relation_counts"] == {"IDENTICAL": 1, "STRICT_PREFIX_EXTENSION": 1, "NOT_PREFIX_EXTENSION": 1}
    assert first["strict_prefix_extension_suffix_total"] == 2
    assert first["base_e146_sequence_sha256"] == _digest("s1")
    assert first["candidate_e146_sequence_sha256"] == _digest("s4")
    assert e148.verify_startup_readiness_e148_e147_comparison_sequence(first) == first


def test_e148_rejects_minimum_duplicate_and_broken_adjacency() -> None:
    one = [_comparison("c1", "s1", "s2")]
    with pytest.raises(ValueError, match="at least two"):
        e148.build_startup_readiness_e148_e147_comparison_sequence(one)
    duplicate = [_comparison("same", "s1", "s2"), _comparison("same", "s2", "s3")]
    with pytest.raises(ValueError, match="duplicate"):
        e148.build_startup_readiness_e148_e147_comparison_sequence(duplicate)
    broken = [_comparison("c1", "s1", "s2"), _comparison("c2", "other", "s3")]
    with pytest.raises(ValueError, match="adjacency"):
        e148.build_startup_readiness_e148_e147_comparison_sequence(broken)


def test_e148_propagates_nested_e147_rejection() -> None:
    with pytest.raises(ValueError, match="nested E147 rejected"):
        e148.build_startup_readiness_e148_e147_comparison_sequence([
            _comparison("c1", "s1", "s2"), {"reject": True}
        ])


@pytest.mark.parametrize("field,value", [
    ("comparison_count", 99),
    ("base_e146_sequence_sha256", "0" * 64),
    ("strict_prefix_extension_suffix_total", 99),
])
def test_e148_rejects_semantic_forgery(field: str, value: object) -> None:
    record = e148.build_startup_readiness_e148_e147_comparison_sequence([
        _comparison("c1", "s1", "s2", "STRICT_PREFIX_EXTENSION", 1),
        _comparison("c2", "s2", "s3"),
    ])
    record[field] = value
    with pytest.raises(ValueError):
        e148.verify_startup_readiness_e148_e147_comparison_sequence(record)


def test_e148_rejects_malformed_identity_boundary_authority_and_digest() -> None:
    original = e148.build_startup_readiness_e148_e147_comparison_sequence([
        _comparison("c1", "s1", "s2"), _comparison("c2", "s2", "s3")
    ])
    mutations = []
    bad_id = deepcopy(original); bad_id["comparisons"][0]["comparison_sha256"] = "bad"; mutations.append(bad_id)
    no_boundary = deepcopy(original); no_boundary["truth_boundaries"] = []; mutations.append(no_boundary)
    authority = deepcopy(original); authority["authority"]["production_deployment_authorized"] = True; mutations.append(authority)
    digest = deepcopy(original); digest["sequence_sha256"] = "0" * 64; mutations.append(digest)
    for record in mutations:
        with pytest.raises(ValueError):
            e148.verify_startup_readiness_e148_e147_comparison_sequence(record)
