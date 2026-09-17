from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e166_e165_comparison_sequence_evidence as e166


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _comparison(label: str, base: str, candidate: str, relation: str = "IDENTICAL", suffix: list[str] | None = None) -> dict[str, object]:
    suffix_ids = [_digest(value) for value in (suffix or [])]
    return {
        "comparison_sha256": _digest(label),
        "base_e164_sequence_sha256": _digest(base),
        "candidate_e164_sequence_sha256": _digest(candidate),
        "relation": relation,
        "extension_comparison_sha256s": suffix_ids,
        "extension_comparison_count": len(suffix_ids),
    }


@pytest.fixture(autouse=True)
def isolate_e165_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E165 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e166, "verify_startup_readiness_e165_e164_sequence_prefix_comparison", verify)


def test_e166_builds_replays_summarizes_and_binds_endpoints_deterministically() -> None:
    first = _comparison("cmp1", "s1", "s2", "STRICT_PREFIX_EXTENSION", ["x", "y"])
    second = _comparison("cmp2", "s2", "s3", "NOT_PREFIX_EXTENSION")
    record = e166.build_startup_readiness_e166_e165_comparison_sequence([first, second])
    assert record["comparison_sha256s"] == [_digest("cmp1"), _digest("cmp2")]
    assert record["comparison_count"] == 2
    assert record["start_e164_sequence_sha256"] == _digest("s1")
    assert record["end_e164_sequence_sha256"] == _digest("s3")
    assert record["relation_counts"] == {"IDENTICAL": 0, "STRICT_PREFIX_EXTENSION": 1, "NOT_PREFIX_EXTENSION": 1}
    assert record["strict_prefix_extension_e163_suffix_total"] == 2
    assert e166.verify_startup_readiness_e166_e165_comparison_sequence(record) == record


def test_e166_rejects_short_nested_duplicate_malformed_and_broken_adjacency() -> None:
    first = _comparison("cmp1", "s1", "s2")
    second = _comparison("cmp2", "s2", "s3")
    with pytest.raises(ValueError, match="at least two"):
        e166.build_startup_readiness_e166_e165_comparison_sequence([first])
    with pytest.raises(ValueError, match="nested E165 rejected"):
        e166.build_startup_readiness_e166_e165_comparison_sequence([first, {"reject": True}])
    duplicate = deepcopy(first)
    duplicate["base_e164_sequence_sha256"] = _digest("s2")
    duplicate["candidate_e164_sequence_sha256"] = _digest("s3")
    with pytest.raises(ValueError, match="unique E165"):
        e166.build_startup_readiness_e166_e165_comparison_sequence([first, duplicate])
    malformed = deepcopy(second); malformed["comparison_sha256"] = "bad"
    with pytest.raises(ValueError, match="valid E165"):
        e166.build_startup_readiness_e166_e165_comparison_sequence([first, malformed])
    broken = _comparison("cmp2", "other", "s3")
    with pytest.raises(ValueError, match="adjacency"):
        e166.build_startup_readiness_e166_e165_comparison_sequence([first, broken])


def test_e166_rejects_relation_suffix_summary_endpoint_boundary_authority_embedded_and_digest_tampering() -> None:
    original = e166.build_startup_readiness_e166_e165_comparison_sequence([
        _comparison("cmp1", "s1", "s2", "STRICT_PREFIX_EXTENSION", ["x"]),
        _comparison("cmp2", "s2", "s3"),
    ])
    mutations = []
    relation = deepcopy(original); relation["comparisons"][0]["relation"] = "IDENTICAL"; mutations.append(relation)
    suffix = deepcopy(original); suffix["comparisons"][0]["extension_comparison_sha256s"] = []; mutations.append(suffix)
    summary = deepcopy(original); summary["relation_counts"]["IDENTICAL"] = 99; mutations.append(summary)
    total = deepcopy(original); total["strict_prefix_extension_e163_suffix_total"] = 99; mutations.append(total)
    endpoint = deepcopy(original); endpoint["end_e164_sequence_sha256"] = _digest("other"); mutations.append(endpoint)
    no_boundary = deepcopy(original); no_boundary["truth_boundaries"] = []; mutations.append(no_boundary)
    authority = deepcopy(original); authority["authority"]["activation_allowed"] = True; mutations.append(authority)
    embedded = deepcopy(original); embedded["comparisons"][1]["candidate_e164_sequence_sha256"] = _digest("other"); mutations.append(embedded)
    digest = deepcopy(original); digest["sequence_sha256"] = "0" * 64; mutations.append(digest)
    for record in mutations:
        with pytest.raises(ValueError):
            e166.verify_startup_readiness_e166_e165_comparison_sequence(record)
