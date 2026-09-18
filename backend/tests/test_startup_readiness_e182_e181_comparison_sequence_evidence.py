from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e182_e181_comparison_sequence_evidence as e182


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _comparison(label: str, base: str, candidate: str, relation: str = "IDENTICAL", suffix: list[str] | None = None) -> dict[str, object]:
    suffix_ids = [_digest(value) for value in (suffix or [])]
    return {
        "comparison_sha256": _digest(label),
        "base_e180_sequence_sha256": _digest(base),
        "candidate_e180_sequence_sha256": _digest(candidate),
        "relation": relation,
        "extension_comparison_sha256s": suffix_ids,
        "extension_comparison_count": len(suffix_ids),
    }


@pytest.fixture(autouse=True)
def isolate_e181_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E181 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e182, "verify_startup_readiness_e181_e180_sequence_prefix_comparison", verify)


def test_e182_builds_replays_and_summarizes_deterministically() -> None:
    comparisons = [
        _comparison("c1", "s0", "s1", "STRICT_PREFIX_EXTENSION", ["e179-a", "e179-b"]),
        _comparison("c2", "s1", "s2", "IDENTICAL"),
        _comparison("c3", "s2", "s3", "NOT_PREFIX_EXTENSION"),
    ]
    record = e182.build_startup_readiness_e182_e181_comparison_sequence(comparisons)
    assert record["comparison_count"] == 3
    assert record["comparison_sha256s"] == [_digest("c1"), _digest("c2"), _digest("c3")]
    assert record["start_e180_sequence_sha256"] == _digest("s0")
    assert record["end_e180_sequence_sha256"] == _digest("s3")
    assert record["relation_counts"] == {"IDENTICAL": 1, "STRICT_PREFIX_EXTENSION": 1, "NOT_PREFIX_EXTENSION": 1}
    assert record["strict_prefix_extension_e179_suffix_total"] == 2
    assert e182.verify_startup_readiness_e182_e181_comparison_sequence(record) == record


def test_e182_rejects_minimum_nested_identity_duplicate_and_adjacency_failures() -> None:
    c1 = _comparison("c1", "s0", "s1")
    with pytest.raises(ValueError, match="at least two"):
        e182.build_startup_readiness_e182_e181_comparison_sequence([c1])
    with pytest.raises(ValueError, match="nested E181 rejected"):
        e182.build_startup_readiness_e182_e181_comparison_sequence([c1, {"reject": True}])
    malformed = _comparison("bad", "s1", "s2"); malformed["comparison_sha256"] = "bad"
    with pytest.raises(ValueError, match="valid E181"):
        e182.build_startup_readiness_e182_e181_comparison_sequence([c1, malformed])
    duplicate = deepcopy(c1); duplicate["base_e180_sequence_sha256"] = _digest("s1"); duplicate["candidate_e180_sequence_sha256"] = _digest("s2")
    with pytest.raises(ValueError, match="unique E181"):
        e182.build_startup_readiness_e182_e181_comparison_sequence([c1, duplicate])
    with pytest.raises(ValueError, match="adjacency"):
        e182.build_startup_readiness_e182_e181_comparison_sequence([c1, _comparison("c2", "wrong", "s2")])


def test_e182_rejects_relation_suffix_summary_boundary_authority_embedded_and_digest_tampering() -> None:
    original = e182.build_startup_readiness_e182_e181_comparison_sequence([
        _comparison("c1", "s0", "s1", "STRICT_PREFIX_EXTENSION", ["e179-a"]),
        _comparison("c2", "s1", "s2", "IDENTICAL"),
    ])
    bad_relation = _comparison("bad-relation", "s1", "s2", "UNSUPPORTED")
    with pytest.raises(ValueError, match="unsupported E181 relation"):
        e182.build_startup_readiness_e182_e181_comparison_sequence([_comparison("c1x", "s0", "s1"), bad_relation])
    illegal_suffix = _comparison("illegal", "s1", "s2", "IDENTICAL", ["x"])
    with pytest.raises(ValueError, match="only for strict-prefix"):
        e182.build_startup_readiness_e182_e181_comparison_sequence([_comparison("c1y", "s0", "s1"), illegal_suffix])
    bad_count = _comparison("bad-count", "s1", "s2", "STRICT_PREFIX_EXTENSION", ["x"]); bad_count["extension_comparison_count"] = 2
    with pytest.raises(ValueError, match="consistent E181 suffix"):
        e182.build_startup_readiness_e182_e181_comparison_sequence([_comparison("c1z", "s0", "s1"), bad_count])
    mutations = []
    summary = deepcopy(original); summary["relation_counts"]["IDENTICAL"] = 99; mutations.append(summary)
    endpoint = deepcopy(original); endpoint["end_e180_sequence_sha256"] = _digest("other"); mutations.append(endpoint)
    boundary = deepcopy(original); boundary["truth_boundaries"] = []; mutations.append(boundary)
    authority = deepcopy(original); authority["authority"]["activation_allowed"] = True; mutations.append(authority)
    embedded = deepcopy(original); embedded["comparisons"][1]["candidate_e180_sequence_sha256"] = _digest("other"); mutations.append(embedded)
    digest = deepcopy(original); digest["sequence_sha256"] = "0" * 64; mutations.append(digest)
    for record in mutations:
        with pytest.raises(ValueError):
            e182.verify_startup_readiness_e182_e181_comparison_sequence(record)
