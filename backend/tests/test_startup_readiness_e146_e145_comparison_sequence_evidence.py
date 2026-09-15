from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e146_e145_comparison_sequence_evidence as e146


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _comparison(label: str, base: str, candidate: str, relation: str = "IDENTICAL", suffix: int = 0) -> dict[str, object]:
    return {
        "comparison_sha256": _digest(label),
        "base_e144_sequence_sha256": _digest(base),
        "candidate_e144_sequence_sha256": _digest(candidate),
        "relation": relation,
        "extension_comparison_count": suffix,
    }


@pytest.fixture(autouse=True)
def isolate_e145_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E145 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e146, "verify_startup_readiness_e145_e144_sequence_prefix_comparison", verify)


def _valid() -> list[dict[str, object]]:
    return [
        _comparison("c1", "s1", "s2", "STRICT_PREFIX_EXTENSION", 2),
        _comparison("c2", "s2", "s3", "IDENTICAL", 0),
    ]


def test_e146_build_and_replay_are_deterministic() -> None:
    first = e146.build_startup_readiness_e146_e145_comparison_sequence(_valid())
    second = e146.build_startup_readiness_e146_e145_comparison_sequence(_valid())
    assert first == second
    assert first["comparison_count"] == 2
    assert first["relation_counts"] == {"IDENTICAL": 1, "STRICT_PREFIX_EXTENSION": 1, "NOT_PREFIX_EXTENSION": 0}
    assert first["strict_prefix_extension_suffix_total"] == 2
    assert e146.verify_startup_readiness_e146_e145_comparison_sequence(first) == first


def test_e146_requires_two_comparisons() -> None:
    with pytest.raises(ValueError, match="at least two"):
        e146.build_startup_readiness_e146_e145_comparison_sequence(_valid()[:1])


def test_e146_rejects_duplicate_identity_and_broken_adjacency() -> None:
    duplicate = _valid()
    duplicate[1]["comparison_sha256"] = duplicate[0]["comparison_sha256"]
    with pytest.raises(ValueError, match="duplicate"):
        e146.build_startup_readiness_e146_e145_comparison_sequence(duplicate)
    broken = _valid()
    broken[1]["base_e144_sequence_sha256"] = _digest("other")
    with pytest.raises(ValueError, match="adjacency"):
        e146.build_startup_readiness_e146_e145_comparison_sequence(broken)


def test_e146_propagates_nested_rejection() -> None:
    rejected = _valid()
    rejected[1]["reject"] = True
    with pytest.raises(ValueError, match="nested E145 rejected"):
        e146.build_startup_readiness_e146_e145_comparison_sequence(rejected)


def test_e146_rejects_semantic_and_digest_tampering() -> None:
    record = e146.build_startup_readiness_e146_e145_comparison_sequence(_valid())
    forged = deepcopy(record)
    forged["comparison_count"] = 3
    with pytest.raises(ValueError, match="comparison_count"):
        e146.verify_startup_readiness_e146_e145_comparison_sequence(forged)
    forged = deepcopy(record)
    forged["sequence_sha256"] = _digest("forged")
    with pytest.raises(ValueError, match="canonical record"):
        e146.verify_startup_readiness_e146_e145_comparison_sequence(forged)


def test_e146_rejects_missing_boundaries_and_authority_escalation() -> None:
    record = e146.build_startup_readiness_e146_e145_comparison_sequence(_valid())
    no_boundaries = deepcopy(record)
    no_boundaries["truth_boundaries"] = []
    with pytest.raises(ValueError, match="truth boundaries"):
        e146.verify_startup_readiness_e146_e145_comparison_sequence(no_boundaries)
    elevated = deepcopy(record)
    elevated["authority"]["activation_allowed"] = True
    with pytest.raises(ValueError, match="activation authority"):
        e146.verify_startup_readiness_e146_e145_comparison_sequence(elevated)


def test_e146_rejects_malformed_identity_on_build() -> None:
    comparisons = _valid()
    comparisons[0]["comparison_sha256"] = "bad"
    with pytest.raises(ValueError, match="malformed"):
        e146.build_startup_readiness_e146_e145_comparison_sequence(comparisons)
