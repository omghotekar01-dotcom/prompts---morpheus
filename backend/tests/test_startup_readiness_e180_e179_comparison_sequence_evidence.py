from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e180_e179_comparison_sequence_evidence as e180


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _comparison(label: str, base: str, candidate: str, relation: str = "IDENTICAL", suffix: list[str] | None = None) -> dict[str, object]:
    suffix_ids = [_digest(value) for value in (suffix or [])]
    return {
        "comparison_sha256": _digest(label),
        "base_e178_sequence_sha256": _digest(base),
        "candidate_e178_sequence_sha256": _digest(candidate),
        "relation": relation,
        "extension_comparison_sha256s": suffix_ids,
        "extension_comparison_count": len(suffix_ids),
    }


@pytest.fixture(autouse=True)
def isolate_e179_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E179 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e180, "verify_startup_readiness_e179_e178_sequence_prefix_comparison", verify)


def test_e180_builds_replays_and_summarizes_deterministically() -> None:
    comparisons = [
        _comparison("a", "s0", "s1"),
        _comparison("b", "s1", "s2", "STRICT_PREFIX_EXTENSION", ["x", "y"]),
        _comparison("c", "s2", "s3", "NOT_PREFIX_EXTENSION"),
    ]
    record = e180.build_startup_readiness_e180_e179_comparison_sequence(comparisons)
    assert record["comparison_count"] == 3
    assert record["comparison_sha256s"] == [_digest("a"), _digest("b"), _digest("c")]
    assert record["start_e178_sequence_sha256"] == _digest("s0")
    assert record["end_e178_sequence_sha256"] == _digest("s3")
    assert record["relation_counts"] == {"IDENTICAL": 1, "STRICT_PREFIX_EXTENSION": 1, "NOT_PREFIX_EXTENSION": 1}
    assert record["strict_prefix_extension_e177_suffix_total"] == 2
    assert e180.verify_startup_readiness_e180_e179_comparison_sequence(record) == record


def test_e180_rejects_minimum_nested_identity_duplicate_and_adjacency_failures() -> None:
    a = _comparison("a", "s0", "s1")
    b = _comparison("b", "s1", "s2")
    with pytest.raises(ValueError, match="at least two"):
        e180.build_startup_readiness_e180_e179_comparison_sequence([a])
    with pytest.raises(ValueError, match="nested E179 rejected"):
        e180.build_startup_readiness_e180_e179_comparison_sequence([a, {"reject": True}])
    malformed = deepcopy(b); malformed["comparison_sha256"] = "bad"
    with pytest.raises(ValueError, match="valid E179"):
        e180.build_startup_readiness_e180_e179_comparison_sequence([a, malformed])
    duplicate = deepcopy(b); duplicate["comparison_sha256"] = a["comparison_sha256"]
    with pytest.raises(ValueError, match="unique E179"):
        e180.build_startup_readiness_e180_e179_comparison_sequence([a, duplicate])
    broken = _comparison("b", "other", "s2")
    with pytest.raises(ValueError, match="adjacency"):
        e180.build_startup_readiness_e180_e179_comparison_sequence([a, broken])


def test_e180_rejects_relation_and_suffix_semantic_failures() -> None:
    a = _comparison("a", "s0", "s1")
    unsupported = _comparison("b", "s1", "s2", "UNKNOWN")
    with pytest.raises(ValueError, match="unsupported E179 relation"):
        e180.build_startup_readiness_e180_e179_comparison_sequence([a, unsupported])
    illegal_suffix = _comparison("b", "s1", "s2", "IDENTICAL", ["x"])
    with pytest.raises(ValueError, match="only for strict-prefix"):
        e180.build_startup_readiness_e180_e179_comparison_sequence([a, illegal_suffix])
    inconsistent = _comparison("b", "s1", "s2", "STRICT_PREFIX_EXTENSION", ["x"]); inconsistent["extension_comparison_count"] = 2
    with pytest.raises(ValueError, match="consistent E179 suffix"):
        e180.build_startup_readiness_e180_e179_comparison_sequence([a, inconsistent])


def test_e180_rejects_summary_endpoint_boundary_authority_embedded_and_digest_tampering() -> None:
    original = e180.build_startup_readiness_e180_e179_comparison_sequence([
        _comparison("a", "s0", "s1"),
        _comparison("b", "s1", "s2", "STRICT_PREFIX_EXTENSION", ["x"]),
    ])
    mutations = []
    count = deepcopy(original); count["comparison_count"] = 99; mutations.append(count)
    summary = deepcopy(original); summary["relation_counts"]["IDENTICAL"] = 9; mutations.append(summary)
    suffix_total = deepcopy(original); suffix_total["strict_prefix_extension_e177_suffix_total"] = 9; mutations.append(suffix_total)
    endpoint = deepcopy(original); endpoint["end_e178_sequence_sha256"] = _digest("other"); mutations.append(endpoint)
    no_boundary = deepcopy(original); no_boundary["truth_boundaries"] = []; mutations.append(no_boundary)
    authority = deepcopy(original); authority["authority"]["automatic_control_allowed"] = True; mutations.append(authority)
    embedded = deepcopy(original); embedded["comparisons"][1]["relation"] = "IDENTICAL"; mutations.append(embedded)
    digest = deepcopy(original); digest["sequence_sha256"] = "0" * 64; mutations.append(digest)
    for record in mutations:
        with pytest.raises(ValueError):
            e180.verify_startup_readiness_e180_e179_comparison_sequence(record)
