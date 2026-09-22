from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e222_e221_comparison_sequence_evidence as e222


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _comparison(label: str, base: str, candidate: str, relation: str = "IDENTICAL", suffix: list[str] | None = None) -> dict[str, object]:
    suffix = suffix or []
    return {
        "comparison_sha256": _digest(label),
        "base_e220_sequence_sha256": _digest(base),
        "candidate_e220_sequence_sha256": _digest(candidate),
        "relation": relation,
        "extension_comparison_sha256s": [_digest(value) for value in suffix],
        "extension_comparison_count": len(suffix),
    }


@pytest.fixture(autouse=True)
def isolate_e221_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E221 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e222, "verify_startup_readiness_e221_e220_sequence_prefix_comparison", verify)


def test_e222_replays_sequence_and_derives_summaries() -> None:
    first = _comparison("c1", "s1", "s2", "STRICT_PREFIX_EXTENSION", ["p1", "p2"])
    second = _comparison("c2", "s2", "s3", "NOT_PREFIX_EXTENSION")
    record = e222.build_startup_readiness_e222_e221_comparison_sequence([first, second])
    assert record["comparison_sha256s"] == [_digest("c1"), _digest("c2")]
    assert record["comparison_count"] == 2
    assert record["start_e220_sequence_sha256"] == _digest("s1")
    assert record["end_e220_sequence_sha256"] == _digest("s3")
    assert record["relation_counts"] == {"IDENTICAL": 0, "STRICT_PREFIX_EXTENSION": 1, "NOT_PREFIX_EXTENSION": 1}
    assert record["strict_prefix_extension_e219_suffix_total"] == 2
    assert e222.verify_startup_readiness_e222_e221_comparison_sequence(record) == record


def test_e222_rejects_minimum_nested_identity_and_adjacency_failures() -> None:
    first = _comparison("c1", "s1", "s2")
    second = _comparison("c2", "s2", "s3")
    with pytest.raises(ValueError, match="at least two"):
        e222.build_startup_readiness_e222_e221_comparison_sequence([first])
    with pytest.raises(ValueError, match="nested E221 rejected"):
        e222.build_startup_readiness_e222_e221_comparison_sequence([first, {"reject": True}])
    malformed = deepcopy(second); malformed["comparison_sha256"] = "bad"
    with pytest.raises(ValueError, match="valid E221"):
        e222.build_startup_readiness_e222_e221_comparison_sequence([first, malformed])
    duplicate = deepcopy(second); duplicate["comparison_sha256"] = first["comparison_sha256"]
    with pytest.raises(ValueError, match="unique E221"):
        e222.build_startup_readiness_e222_e221_comparison_sequence([first, duplicate])
    broken = _comparison("c2", "other", "s3")
    with pytest.raises(ValueError, match="adjacency"):
        e222.build_startup_readiness_e222_e221_comparison_sequence([first, broken])


def test_e222_rejects_relation_suffix_summary_boundary_authority_embedded_and_digest_tampering() -> None:
    first = _comparison("c1", "s1", "s2", "STRICT_PREFIX_EXTENSION", ["p1"])
    second = _comparison("c2", "s2", "s3")
    original = e222.build_startup_readiness_e222_e221_comparison_sequence([first, second])
    unsupported = deepcopy(second); unsupported["relation"] = "UNKNOWN"
    with pytest.raises(ValueError, match="unsupported"):
        e222.build_startup_readiness_e222_e221_comparison_sequence([first, unsupported])
    illegal_suffix = deepcopy(second); illegal_suffix["extension_comparison_sha256s"] = [_digest("p2")]; illegal_suffix["extension_comparison_count"] = 1
    with pytest.raises(ValueError, match="only for strict-prefix"):
        e222.build_startup_readiness_e222_e221_comparison_sequence([first, illegal_suffix])
    mutations = []
    summary = deepcopy(original); summary["relation_counts"]["IDENTICAL"] = 9; mutations.append(summary)
    endpoint = deepcopy(original); endpoint["end_e220_sequence_sha256"] = _digest("other"); mutations.append(endpoint)
    boundary = deepcopy(original); boundary["truth_boundaries"] = []; mutations.append(boundary)
    authority = deepcopy(original); authority["authority"]["activation_allowed"] = True; mutations.append(authority)
    embedded = deepcopy(original); embedded["comparisons"][1]["candidate_e220_sequence_sha256"] = _digest("other"); mutations.append(embedded)
    digest = deepcopy(original); digest["sequence_sha256"] = "0" * 64; mutations.append(digest)
    for record in mutations:
        with pytest.raises(ValueError):
            e222.verify_startup_readiness_e222_e221_comparison_sequence(record)
