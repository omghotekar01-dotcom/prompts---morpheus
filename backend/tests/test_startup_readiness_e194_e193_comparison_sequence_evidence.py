from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e194_e193_comparison_sequence_evidence as e194


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _comparison(label: str, base: str, candidate: str, relation: str = "IDENTICAL", suffix: list[str] | None = None) -> dict[str, object]:
    suffix_ids = [_digest(value) for value in (suffix or [])]
    return {
        "comparison_sha256": _digest(label),
        "base_e192_sequence_sha256": _digest(base),
        "candidate_e192_sequence_sha256": _digest(candidate),
        "relation": relation,
        "extension_comparison_sha256s": suffix_ids,
        "extension_comparison_count": len(suffix_ids),
    }


@pytest.fixture(autouse=True)
def isolate_e193_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E193 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e194, "verify_startup_readiness_e193_e192_sequence_prefix_comparison", verify)


def test_e194_builds_and_replays_deterministic_sequence_summary() -> None:
    first = _comparison("p1", "s1", "s2", "STRICT_PREFIX_EXTENSION", ["c3", "c4"])
    second = _comparison("p2", "s2", "s3", "IDENTICAL")
    third = _comparison("p3", "s3", "s4", "NOT_PREFIX_EXTENSION")
    record = e194.build_startup_readiness_e194_e193_comparison_sequence([first, second, third])
    assert record["comparison_sha256s"] == [_digest("p1"), _digest("p2"), _digest("p3")]
    assert record["comparison_count"] == 3
    assert record["start_e192_sequence_sha256"] == _digest("s1")
    assert record["end_e192_sequence_sha256"] == _digest("s4")
    assert record["relation_counts"] == {"IDENTICAL": 1, "STRICT_PREFIX_EXTENSION": 1, "NOT_PREFIX_EXTENSION": 1}
    assert record["strict_prefix_extension_e191_suffix_total"] == 2
    assert e194.verify_startup_readiness_e194_e193_comparison_sequence(record) == record


def test_e194_rejects_minimum_nested_identity_duplicate_and_adjacency_failures() -> None:
    first = _comparison("p1", "s1", "s2")
    with pytest.raises(ValueError, match="at least two"):
        e194.build_startup_readiness_e194_e193_comparison_sequence([first])
    with pytest.raises(ValueError, match="nested E193 rejected"):
        e194.build_startup_readiness_e194_e193_comparison_sequence([first, {"reject": True}])
    malformed = _comparison("p2", "s2", "s3"); malformed["comparison_sha256"] = "bad"
    with pytest.raises(ValueError, match="valid E193"):
        e194.build_startup_readiness_e194_e193_comparison_sequence([first, malformed])
    duplicate = deepcopy(first); duplicate["base_e192_sequence_sha256"] = _digest("s2"); duplicate["candidate_e192_sequence_sha256"] = _digest("s3")
    with pytest.raises(ValueError, match="unique E193"):
        e194.build_startup_readiness_e194_e193_comparison_sequence([first, duplicate])
    nonadjacent = _comparison("p2", "other", "s3")
    with pytest.raises(ValueError, match="adjacency"):
        e194.build_startup_readiness_e194_e193_comparison_sequence([first, nonadjacent])


def test_e194_rejects_relation_and_suffix_semantic_failures() -> None:
    first = _comparison("p1", "s1", "s2")
    unsupported = _comparison("p2", "s2", "s3", "UNSUPPORTED")
    with pytest.raises(ValueError, match="unsupported"):
        e194.build_startup_readiness_e194_e193_comparison_sequence([first, unsupported])
    illegal_suffix = _comparison("p2", "s2", "s3", "IDENTICAL", ["c3"])
    with pytest.raises(ValueError, match="only for strict-prefix"):
        e194.build_startup_readiness_e194_e193_comparison_sequence([first, illegal_suffix])
    inconsistent = _comparison("p2", "s2", "s3", "STRICT_PREFIX_EXTENSION", ["c3"]); inconsistent["extension_comparison_count"] = 2
    with pytest.raises(ValueError, match="consistent"):
        e194.build_startup_readiness_e194_e193_comparison_sequence([first, inconsistent])


def test_e194_rejects_summary_endpoint_boundary_authority_embedded_and_digest_tampering() -> None:
    original = e194.build_startup_readiness_e194_e193_comparison_sequence([
        _comparison("p1", "s1", "s2", "STRICT_PREFIX_EXTENSION", ["c3"]),
        _comparison("p2", "s2", "s3"),
    ])
    mutations = []
    summary = deepcopy(original); summary["relation_counts"]["IDENTICAL"] = 99; mutations.append(summary)
    suffix_total = deepcopy(original); suffix_total["strict_prefix_extension_e191_suffix_total"] = 99; mutations.append(suffix_total)
    endpoint = deepcopy(original); endpoint["end_e192_sequence_sha256"] = _digest("other"); mutations.append(endpoint)
    boundary = deepcopy(original); boundary["truth_boundaries"] = []; mutations.append(boundary)
    authority = deepcopy(original); authority["authority"]["activation_allowed"] = True; mutations.append(authority)
    embedded = deepcopy(original); embedded["comparisons"][1]["candidate_e192_sequence_sha256"] = _digest("other"); mutations.append(embedded)
    digest = deepcopy(original); digest["sequence_sha256"] = "0" * 64; mutations.append(digest)
    for record in mutations:
        with pytest.raises(ValueError):
            e194.verify_startup_readiness_e194_e193_comparison_sequence(record)