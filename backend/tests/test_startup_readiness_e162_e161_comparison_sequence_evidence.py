from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e162_e161_comparison_sequence_evidence as e162


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _comparison(label: str, base: str, candidate: str, relation: str = "IDENTICAL", suffix: int = 0) -> dict[str, object]:
    return {
        "comparison_sha256": _digest(label),
        "base_e160_sequence_sha256": _digest(base),
        "candidate_e160_sequence_sha256": _digest(candidate),
        "relation": relation,
        "extension_comparison_count": suffix,
    }


@pytest.fixture(autouse=True)
def isolate_e161_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E161 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e162, "verify_startup_readiness_e161_e160_sequence_prefix_comparison", verify)


def test_e162_builds_replays_and_summarizes_deterministically() -> None:
    comparisons = [
        _comparison("c1", "s1", "s2", "STRICT_PREFIX_EXTENSION", 2),
        _comparison("c2", "s2", "s3", "IDENTICAL", 0),
        _comparison("c3", "s3", "s4", "NOT_PREFIX_EXTENSION", 0),
    ]
    first = e162.build_startup_readiness_e162_e161_comparison_sequence(comparisons)
    second = e162.build_startup_readiness_e162_e161_comparison_sequence(deepcopy(comparisons))
    assert first == second
    assert first["comparison_count"] == 3
    assert first["relation_counts"] == {"IDENTICAL": 1, "STRICT_PREFIX_EXTENSION": 1, "NOT_PREFIX_EXTENSION": 1}
    assert first["strict_prefix_extension_e159_comparison_total"] == 2
    assert first["start_e160_sequence_sha256"] == _digest("s1")
    assert first["end_e160_sequence_sha256"] == _digest("s4")
    assert e162.verify_startup_readiness_e162_e161_comparison_sequence(first) == first


def test_e162_rejects_minimum_duplicate_malformed_nested_and_broken_adjacency() -> None:
    c1 = _comparison("c1", "s1", "s2")
    c2 = _comparison("c2", "s2", "s3")
    with pytest.raises(ValueError, match="at least two"):
        e162.build_startup_readiness_e162_e161_comparison_sequence([c1])
    duplicate = deepcopy(c2); duplicate["comparison_sha256"] = c1["comparison_sha256"]
    with pytest.raises(ValueError, match="unique valid"):
        e162.build_startup_readiness_e162_e161_comparison_sequence([c1, duplicate])
    malformed = deepcopy(c2); malformed["comparison_sha256"] = "bad"
    with pytest.raises(ValueError, match="unique valid"):
        e162.build_startup_readiness_e162_e161_comparison_sequence([c1, malformed])
    with pytest.raises(ValueError, match="nested E161 rejected"):
        e162.build_startup_readiness_e162_e161_comparison_sequence([c1, {"reject": True}])
    broken = _comparison("c2", "other", "s3")
    with pytest.raises(ValueError, match="broken E160 adjacency"):
        e162.build_startup_readiness_e162_e161_comparison_sequence([c1, broken])


def test_e162_rejects_invalid_relation_and_suffix_semantics() -> None:
    c1 = _comparison("c1", "s1", "s2")
    bad_relation = _comparison("c2", "s2", "s3", "UNKNOWN", 0)
    with pytest.raises(ValueError, match="unsupported E161 relation"):
        e162.build_startup_readiness_e162_e161_comparison_sequence([c1, bad_relation])
    bad_suffix = _comparison("c2", "s2", "s3", "IDENTICAL", 1)
    with pytest.raises(ValueError, match="inconsistent strict-prefix"):
        e162.build_startup_readiness_e162_e161_comparison_sequence([c1, bad_suffix])
    bool_suffix = _comparison("c2", "s2", "s3", "STRICT_PREFIX_EXTENSION", 1); bool_suffix["extension_comparison_count"] = True
    with pytest.raises(ValueError, match="invalid strict-prefix"):
        e162.build_startup_readiness_e162_e161_comparison_sequence([c1, bool_suffix])


def test_e162_rejects_summary_boundary_authority_embedded_and_digest_tampering() -> None:
    original = e162.build_startup_readiness_e162_e161_comparison_sequence([
        _comparison("c1", "s1", "s2", "STRICT_PREFIX_EXTENSION", 2),
        _comparison("c2", "s2", "s3"),
    ])
    mutations = []
    count = deepcopy(original); count["comparison_count"] = 99; mutations.append(count)
    summary = deepcopy(original); summary["relation_counts"]["IDENTICAL"] = 99; mutations.append(summary)
    suffix = deepcopy(original); suffix["strict_prefix_extension_e159_comparison_total"] = 99; mutations.append(suffix)
    endpoint = deepcopy(original); endpoint["end_e160_sequence_sha256"] = _digest("other"); mutations.append(endpoint)
    no_boundary = deepcopy(original); no_boundary["truth_boundaries"] = []; mutations.append(no_boundary)
    authority = deepcopy(original); authority["authority"]["activation_allowed"] = True; mutations.append(authority)
    embedded = deepcopy(original); embedded["comparisons"][1]["candidate_e160_sequence_sha256"] = _digest("other"); mutations.append(embedded)
    digest = deepcopy(original); digest["sequence_sha256"] = "0" * 64; mutations.append(digest)
    for record in mutations:
        with pytest.raises(ValueError):
            e162.verify_startup_readiness_e162_e161_comparison_sequence(record)
