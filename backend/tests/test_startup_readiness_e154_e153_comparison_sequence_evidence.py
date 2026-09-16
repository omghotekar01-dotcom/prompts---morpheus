from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e154_e153_comparison_sequence_evidence as e154


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _comparison(label: str, base: str, candidate: str, relation: str = "IDENTICAL", suffix: int = 0) -> dict[str, object]:
    return {
        "comparison_sha256": _digest(label),
        "base_e152_sequence_sha256": _digest(base),
        "candidate_e152_sequence_sha256": _digest(candidate),
        "relation": relation,
        "extension_comparison_count": suffix,
    }


@pytest.fixture(autouse=True)
def isolate_e153_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E153 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e154, "verify_startup_readiness_e153_e152_sequence_prefix_comparison", verify)


def test_e154_replays_deterministically_and_summarizes_relations() -> None:
    comparisons = [
        _comparison("c1", "s1", "s2", "STRICT_PREFIX_EXTENSION", 2),
        _comparison("c2", "s2", "s3", "NOT_PREFIX_EXTENSION", 0),
        _comparison("c3", "s3", "s4", "IDENTICAL", 0),
    ]
    first = e154.build_startup_readiness_e154_e153_comparison_sequence(comparisons)
    second = e154.build_startup_readiness_e154_e153_comparison_sequence(deepcopy(comparisons))
    assert first == second
    assert first["relation_counts"] == {"IDENTICAL": 1, "STRICT_PREFIX_EXTENSION": 1, "NOT_PREFIX_EXTENSION": 1}
    assert first["strict_prefix_extension_comparison_total"] == 2
    assert first["start_e152_sequence_sha256"] == _digest("s1")
    assert first["end_e152_sequence_sha256"] == _digest("s4")
    assert e154.verify_startup_readiness_e154_e153_comparison_sequence(first) == first


def test_e154_rejects_too_short_duplicate_malformed_and_nested_rejection() -> None:
    one = _comparison("c1", "s1", "s2")
    with pytest.raises(ValueError, match="at least two"):
        e154.build_startup_readiness_e154_e153_comparison_sequence([one])
    with pytest.raises(ValueError, match="unique valid"):
        e154.build_startup_readiness_e154_e153_comparison_sequence([one, deepcopy(one)])
    malformed = _comparison("c2", "s2", "s3"); malformed["comparison_sha256"] = "bad"
    with pytest.raises(ValueError, match="unique valid"):
        e154.build_startup_readiness_e154_e153_comparison_sequence([one, malformed])
    with pytest.raises(ValueError, match="nested E153 rejected"):
        e154.build_startup_readiness_e154_e153_comparison_sequence([one, {"reject": True}])


def test_e154_rejects_broken_adjacency_and_invalid_suffix_semantics() -> None:
    with pytest.raises(ValueError, match="broken E152 adjacency"):
        e154.build_startup_readiness_e154_e153_comparison_sequence([
            _comparison("c1", "s1", "s2"), _comparison("c2", "other", "s3")
        ])
    with pytest.raises(ValueError, match="inconsistent strict-prefix"):
        e154.build_startup_readiness_e154_e153_comparison_sequence([
            _comparison("c1", "s1", "s2", "IDENTICAL", 1), _comparison("c2", "s2", "s3")
        ])


@pytest.mark.parametrize("field,value", [
    ("comparison_count", 99),
    ("start_e152_sequence_sha256", "0" * 64),
    ("relation_counts", {"IDENTICAL": 99, "STRICT_PREFIX_EXTENSION": 0, "NOT_PREFIX_EXTENSION": 0}),
    ("strict_prefix_extension_comparison_total", 99),
])
def test_e154_rejects_summary_forgery(field: str, value: object) -> None:
    record = e154.build_startup_readiness_e154_e153_comparison_sequence([
        _comparison("c1", "s1", "s2"), _comparison("c2", "s2", "s3")
    ])
    record[field] = value
    with pytest.raises(ValueError):
        e154.verify_startup_readiness_e154_e153_comparison_sequence(record)


def test_e154_rejects_boundary_authority_and_digest_tampering() -> None:
    original = e154.build_startup_readiness_e154_e153_comparison_sequence([
        _comparison("c1", "s1", "s2"), _comparison("c2", "s2", "s3")
    ])
    mutations = []
    no_boundary = deepcopy(original); no_boundary["truth_boundaries"] = []; mutations.append(no_boundary)
    authority = deepcopy(original); authority["authority"]["activation_allowed"] = True; mutations.append(authority)
    digest = deepcopy(original); digest["sequence_sha256"] = "0" * 64; mutations.append(digest)
    ids = deepcopy(original); ids["comparison_sha256s"] = list(reversed(ids["comparison_sha256s"])); mutations.append(ids)
    for record in mutations:
        with pytest.raises(ValueError):
            e154.verify_startup_readiness_e154_e153_comparison_sequence(record)
