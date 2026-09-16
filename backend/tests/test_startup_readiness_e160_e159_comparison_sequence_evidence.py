from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e160_e159_comparison_sequence_evidence as e160


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _comparison(label: str, base: str, candidate: str, relation: str = "IDENTICAL", suffix: int = 0) -> dict[str, object]:
    return {
        "comparison_sha256": _digest(label),
        "base_e158_sequence_sha256": _digest(base),
        "candidate_e158_sequence_sha256": _digest(candidate),
        "relation": relation,
        "extension_comparison_count": suffix,
    }


@pytest.fixture(autouse=True)
def isolate_e159_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E159 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e160, "verify_startup_readiness_e159_e158_sequence_prefix_comparison", verify)


def test_e160_builds_replays_and_summarizes_deterministically() -> None:
    comparisons = [
        _comparison("c1", "s1", "s2"),
        _comparison("c2", "s2", "s3", "STRICT_PREFIX_EXTENSION", 2),
        _comparison("c3", "s3", "s4", "NOT_PREFIX_EXTENSION"),
    ]
    first = e160.build_startup_readiness_e160_e159_comparison_sequence(comparisons)
    second = e160.build_startup_readiness_e160_e159_comparison_sequence(deepcopy(comparisons))
    assert first == second
    assert first["comparison_count"] == 3
    assert first["relation_counts"] == {"IDENTICAL": 1, "STRICT_PREFIX_EXTENSION": 1, "NOT_PREFIX_EXTENSION": 1}
    assert first["strict_prefix_extension_comparison_total"] == 2
    assert first["start_e158_sequence_sha256"] == _digest("s1")
    assert first["end_e158_sequence_sha256"] == _digest("s4")
    assert e160.verify_startup_readiness_e160_e159_comparison_sequence(first) == first


def test_e160_rejects_short_duplicate_malformed_and_broken_adjacency() -> None:
    c1 = _comparison("c1", "s1", "s2")
    with pytest.raises(ValueError, match="at least two"):
        e160.build_startup_readiness_e160_e159_comparison_sequence([c1])
    with pytest.raises(ValueError, match="unique valid"):
        e160.build_startup_readiness_e160_e159_comparison_sequence([c1, deepcopy(c1)])
    malformed = _comparison("c2", "s2", "s3"); malformed["comparison_sha256"] = "bad"
    with pytest.raises(ValueError, match="unique valid"):
        e160.build_startup_readiness_e160_e159_comparison_sequence([c1, malformed])
    with pytest.raises(ValueError, match="broken E158 adjacency"):
        e160.build_startup_readiness_e160_e159_comparison_sequence([c1, _comparison("c2", "other", "s3")])
    with pytest.raises(ValueError, match="nested E159 rejected"):
        e160.build_startup_readiness_e160_e159_comparison_sequence([c1, {"reject": True}])


def test_e160_rejects_invalid_relation_and_suffix_semantics() -> None:
    c1 = _comparison("c1", "s1", "s2")
    with pytest.raises(ValueError, match="unsupported E159 relation"):
        e160.build_startup_readiness_e160_e159_comparison_sequence([c1, _comparison("c2", "s2", "s3", "OTHER")])
    with pytest.raises(ValueError, match="inconsistent strict-prefix"):
        e160.build_startup_readiness_e160_e159_comparison_sequence([c1, _comparison("c2", "s2", "s3", "IDENTICAL", 1)])


def test_e160_rejects_summary_boundary_authority_embedded_and_digest_tampering() -> None:
    original = e160.build_startup_readiness_e160_e159_comparison_sequence([
        _comparison("c1", "s1", "s2"),
        _comparison("c2", "s2", "s3", "STRICT_PREFIX_EXTENSION", 1),
    ])
    mutations = []
    summary = deepcopy(original); summary["comparison_count"] = 99; mutations.append(summary)
    no_boundary = deepcopy(original); no_boundary["truth_boundaries"] = []; mutations.append(no_boundary)
    authority = deepcopy(original); authority["authority"]["activation_allowed"] = True; mutations.append(authority)
    embedded = deepcopy(original); embedded["comparisons"][1]["candidate_e158_sequence_sha256"] = _digest("other"); mutations.append(embedded)
    digest = deepcopy(original); digest["sequence_sha256"] = "0" * 64; mutations.append(digest)
    for record in mutations:
        with pytest.raises(ValueError):
            e160.verify_startup_readiness_e160_e159_comparison_sequence(record)
