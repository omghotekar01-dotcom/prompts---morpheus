from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e150_e149_comparison_sequence_evidence as e150


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _comparison(label: str, base: str, candidate: str, relation: str = "IDENTICAL", suffix: int = 0) -> dict[str, object]:
    return {
        "comparison_sha256": _digest(label),
        "base_e148_sequence_sha256": _digest(base),
        "candidate_e148_sequence_sha256": _digest(candidate),
        "relation": relation,
        "extension_comparison_count": suffix,
    }


@pytest.fixture(autouse=True)
def isolate_e149_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E149 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e150, "verify_startup_readiness_e149_e148_sequence_prefix_comparison", verify)


def test_e150_replays_deterministically_and_summarizes() -> None:
    items = [
        _comparison("c1", "s1", "s2", "STRICT_PREFIX_EXTENSION", 2),
        _comparison("c2", "s2", "s3", "NOT_PREFIX_EXTENSION", 0),
        _comparison("c3", "s3", "s3", "IDENTICAL", 0),
    ]
    first = e150.build_startup_readiness_e150_e149_comparison_sequence(items)
    second = e150.build_startup_readiness_e150_e149_comparison_sequence(deepcopy(items))
    assert first == second
    assert first["comparison_count"] == 3
    assert first["start_e148_sequence_sha256"] == _digest("s1")
    assert first["end_e148_sequence_sha256"] == _digest("s3")
    assert first["relation_counts"] == {"IDENTICAL": 1, "STRICT_PREFIX_EXTENSION": 1, "NOT_PREFIX_EXTENSION": 1}
    assert first["strict_prefix_extension_comparison_total"] == 2
    assert e150.verify_startup_readiness_e150_e149_comparison_sequence(first) == first


def test_e150_rejects_short_duplicate_broken_adjacency_and_nested_rejection() -> None:
    c1 = _comparison("c1", "s1", "s2")
    with pytest.raises(ValueError, match="at least two"):
        e150.build_startup_readiness_e150_e149_comparison_sequence([c1])
    with pytest.raises(ValueError, match="unique valid"):
        e150.build_startup_readiness_e150_e149_comparison_sequence([c1, deepcopy(c1)])
    with pytest.raises(ValueError, match="broken E148 adjacency"):
        e150.build_startup_readiness_e150_e149_comparison_sequence([c1, _comparison("c2", "other", "s3")])
    with pytest.raises(ValueError, match="nested E149 rejected"):
        e150.build_startup_readiness_e150_e149_comparison_sequence([c1, {"reject": True}])


def test_e150_rejects_malformed_identity_and_inconsistent_suffix() -> None:
    c1 = _comparison("c1", "s1", "s2")
    malformed = _comparison("c2", "s2", "s3"); malformed["comparison_sha256"] = "bad"
    with pytest.raises(ValueError, match="unique valid"):
        e150.build_startup_readiness_e150_e149_comparison_sequence([c1, malformed])
    bad_suffix = _comparison("c2", "s2", "s3", "IDENTICAL", 1)
    with pytest.raises(ValueError, match="inconsistent"):
        e150.build_startup_readiness_e150_e149_comparison_sequence([c1, bad_suffix])


@pytest.mark.parametrize("field,value", [
    ("comparison_count", 99),
    ("start_e148_sequence_sha256", "0" * 64),
    ("strict_prefix_extension_comparison_total", 99),
])
def test_e150_rejects_semantic_forgery(field: str, value: object) -> None:
    record = e150.build_startup_readiness_e150_e149_comparison_sequence([
        _comparison("c1", "s1", "s2"), _comparison("c2", "s2", "s3")
    ])
    record[field] = value
    with pytest.raises(ValueError):
        e150.verify_startup_readiness_e150_e149_comparison_sequence(record)


def test_e150_rejects_boundary_authority_and_digest_tampering() -> None:
    original = e150.build_startup_readiness_e150_e149_comparison_sequence([
        _comparison("c1", "s1", "s2"), _comparison("c2", "s2", "s3")
    ])
    mutations = []
    no_boundary = deepcopy(original); no_boundary["truth_boundaries"] = []; mutations.append(no_boundary)
    authority = deepcopy(original); authority["authority"]["activation_allowed"] = True; mutations.append(authority)
    digest = deepcopy(original); digest["sequence_sha256"] = "0" * 64; mutations.append(digest)
    for record in mutations:
        with pytest.raises(ValueError):
            e150.verify_startup_readiness_e150_e149_comparison_sequence(record)
