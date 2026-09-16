from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e152_e151_comparison_sequence_evidence as e152


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _comparison(label: str, base: str, candidate: str, relation: str = "IDENTICAL", suffix: int = 0) -> dict[str, object]:
    return {
        "comparison_sha256": _digest(label),
        "base_e150_sequence_sha256": _digest(base),
        "candidate_e150_sequence_sha256": _digest(candidate),
        "relation": relation,
        "extension_comparison_count": suffix,
    }


@pytest.fixture(autouse=True)
def isolate_e151_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E151 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e152, "verify_startup_readiness_e151_e150_sequence_prefix_comparison", verify)


def test_e152_replays_deterministically_and_summarizes_relations() -> None:
    comparisons = [
        _comparison("c1", "s0", "s1", "IDENTICAL", 0),
        _comparison("c2", "s1", "s2", "STRICT_PREFIX_EXTENSION", 3),
        _comparison("c3", "s2", "s3", "NOT_PREFIX_EXTENSION", 0),
    ]
    first = e152.build_startup_readiness_e152_e151_comparison_sequence(comparisons)
    second = e152.build_startup_readiness_e152_e151_comparison_sequence(deepcopy(comparisons))
    assert first == second
    assert first["comparison_count"] == 3
    assert first["relation_counts"] == {"IDENTICAL": 1, "STRICT_PREFIX_EXTENSION": 1, "NOT_PREFIX_EXTENSION": 1}
    assert first["strict_prefix_extension_comparison_total"] == 3
    assert first["start_e150_sequence_sha256"] == _digest("s0")
    assert first["end_e150_sequence_sha256"] == _digest("s3")
    assert e152.verify_startup_readiness_e152_e151_comparison_sequence(first) == first


def test_e152_rejects_too_short_duplicate_broken_adjacency_and_nested_rejection() -> None:
    one = _comparison("c1", "s0", "s1")
    with pytest.raises(ValueError, match="at least two"):
        e152.build_startup_readiness_e152_e151_comparison_sequence([one])
    with pytest.raises(ValueError, match="unique valid"):
        e152.build_startup_readiness_e152_e151_comparison_sequence([one, deepcopy(one)])
    with pytest.raises(ValueError, match="broken E150 adjacency"):
        e152.build_startup_readiness_e152_e151_comparison_sequence([one, _comparison("c2", "other", "s2")])
    with pytest.raises(ValueError, match="nested E151 rejected"):
        e152.build_startup_readiness_e152_e151_comparison_sequence([one, {"reject": True}])


def test_e152_rejects_malformed_identity_relation_and_suffix_semantics() -> None:
    malformed = _comparison("c1", "s0", "s1"); malformed["comparison_sha256"] = "bad"
    with pytest.raises(ValueError, match="unique valid"):
        e152.build_startup_readiness_e152_e151_comparison_sequence([malformed, _comparison("c2", "s1", "s2")])
    unsupported = [_comparison("c1", "s0", "s1", "UNKNOWN"), _comparison("c2", "s1", "s2")]
    with pytest.raises(ValueError, match="unsupported"):
        e152.build_startup_readiness_e152_e151_comparison_sequence(unsupported)
    inconsistent = [_comparison("c1", "s0", "s1", "IDENTICAL", 1), _comparison("c2", "s1", "s2")]
    with pytest.raises(ValueError, match="inconsistent"):
        e152.build_startup_readiness_e152_e151_comparison_sequence(inconsistent)


def test_e152_fails_closed_on_summary_boundary_authority_and_digest_tampering() -> None:
    original = e152.build_startup_readiness_e152_e151_comparison_sequence([
        _comparison("c1", "s0", "s1"),
        _comparison("c2", "s1", "s2", "STRICT_PREFIX_EXTENSION", 2),
    ])
    mutations = []
    summary = deepcopy(original); summary["comparison_count"] = 99; mutations.append(summary)
    identities = deepcopy(original); identities["comparison_sha256s"] = []; mutations.append(identities)
    boundary = deepcopy(original); boundary["truth_boundaries"] = []; mutations.append(boundary)
    authority = deepcopy(original); authority["authority"]["activation_allowed"] = True; mutations.append(authority)
    digest = deepcopy(original); digest["sequence_sha256"] = "0" * 64; mutations.append(digest)
    for record in mutations:
        with pytest.raises(ValueError):
            e152.verify_startup_readiness_e152_e151_comparison_sequence(record)
