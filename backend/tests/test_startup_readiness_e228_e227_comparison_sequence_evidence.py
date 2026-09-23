from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e228_e227_comparison_sequence_evidence as e228


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _comparison(label: str, base: str, candidate: str, relation: str = "IDENTICAL", suffix: list[str] | None = None) -> dict[str, object]:
    extension = [_digest(value) for value in (suffix or [])]
    return {
        "comparison_sha256": _digest(label),
        "base_e226_sequence_sha256": _digest(base),
        "candidate_e226_sequence_sha256": _digest(candidate),
        "relation": relation,
        "extension_comparison_sha256s": extension,
        "extension_comparison_count": len(extension),
    }


@pytest.fixture(autouse=True)
def isolate_e227_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E227 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e228, "verify_startup_readiness_e227_e226_sequence_prefix_comparison", verify)


def test_e228_replays_ordered_sequence_and_derives_summary() -> None:
    first = _comparison("p1", "s1", "s2")
    second = _comparison("p2", "s2", "s3", "STRICT_PREFIX_EXTENSION", ["c3", "c4"])
    third = _comparison("p3", "s3", "s4", "NOT_PREFIX_EXTENSION")
    record = e228.build_startup_readiness_e228_e227_comparison_sequence([first, second, third])
    assert record["comparison_sha256s"] == [_digest("p1"), _digest("p2"), _digest("p3")]
    assert record["comparison_count"] == 3
    assert record["start_e226_sequence_sha256"] == _digest("s1")
    assert record["end_e226_sequence_sha256"] == _digest("s4")
    assert record["relation_counts"] == {"IDENTICAL": 1, "STRICT_PREFIX_EXTENSION": 1, "NOT_PREFIX_EXTENSION": 1}
    assert record["strict_prefix_extension_e225_suffix_total"] == 2
    assert e228.verify_startup_readiness_e228_e227_comparison_sequence(record) == record


def test_e228_rejects_minimum_nested_malformed_duplicate_and_broken_adjacency() -> None:
    first = _comparison("p1", "s1", "s2")
    with pytest.raises(ValueError, match="at least two"):
        e228.build_startup_readiness_e228_e227_comparison_sequence([first])
    with pytest.raises(ValueError, match="nested E227 rejected"):
        e228.build_startup_readiness_e228_e227_comparison_sequence([first, {"reject": True}])
    malformed = _comparison("p2", "s2", "s3"); malformed["comparison_sha256"] = "bad"
    with pytest.raises(ValueError, match="valid E227"):
        e228.build_startup_readiness_e228_e227_comparison_sequence([first, malformed])
    duplicate = deepcopy(first); duplicate["base_e226_sequence_sha256"] = _digest("s2"); duplicate["candidate_e226_sequence_sha256"] = _digest("s3")
    with pytest.raises(ValueError, match="unique E227"):
        e228.build_startup_readiness_e228_e227_comparison_sequence([first, duplicate])
    broken = _comparison("p2", "other", "s3")
    with pytest.raises(ValueError, match="adjacency"):
        e228.build_startup_readiness_e228_e227_comparison_sequence([first, broken])


def test_e228_rejects_relation_and_suffix_semantic_errors() -> None:
    first = _comparison("p1", "s1", "s2")
    unsupported = _comparison("p2", "s2", "s3", "NEWER")
    with pytest.raises(ValueError, match="unsupported"):
        e228.build_startup_readiness_e228_e227_comparison_sequence([first, unsupported])
    illegal_suffix = _comparison("p2", "s2", "s3", "IDENTICAL", ["c3"])
    with pytest.raises(ValueError, match="only for strict-prefix"):
        e228.build_startup_readiness_e228_e227_comparison_sequence([first, illegal_suffix])
    bad_count = _comparison("p2", "s2", "s3", "STRICT_PREFIX_EXTENSION", ["c3"]); bad_count["extension_comparison_count"] = 2
    with pytest.raises(ValueError, match="consistent E227 suffix"):
        e228.build_startup_readiness_e228_e227_comparison_sequence([first, bad_count])


def test_e228_rejects_summary_endpoint_boundary_authority_embedded_and_digest_tampering() -> None:
    first = _comparison("p1", "s1", "s2")
    second = _comparison("p2", "s2", "s3", "STRICT_PREFIX_EXTENSION", ["c3"])
    original = e228.build_startup_readiness_e228_e227_comparison_sequence([first, second])
    mutations = []
    summary = deepcopy(original); summary["relation_counts"]["IDENTICAL"] = 9; mutations.append(summary)
    total = deepcopy(original); total["strict_prefix_extension_e225_suffix_total"] = 9; mutations.append(total)
    endpoint = deepcopy(original); endpoint["end_e226_sequence_sha256"] = _digest("other"); mutations.append(endpoint)
    boundary = deepcopy(original); boundary["truth_boundaries"] = []; mutations.append(boundary)
    authority = deepcopy(original); authority["authority"]["activation_allowed"] = True; mutations.append(authority)
    embedded = deepcopy(original); embedded["comparisons"][1]["relation"] = "IDENTICAL"; mutations.append(embedded)
    digest = deepcopy(original); digest["sequence_sha256"] = "0" * 64; mutations.append(digest)
    for record in mutations:
        with pytest.raises(ValueError):
            e228.verify_startup_readiness_e228_e227_comparison_sequence(record)
