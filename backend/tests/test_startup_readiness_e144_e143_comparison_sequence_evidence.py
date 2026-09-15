from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e144_e143_comparison_sequence_evidence as e144


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _comparison(label: str, base: str, candidate: str, relation: str = "IDENTICAL", suffix: int = 0) -> dict[str, object]:
    return {
        "comparison_sha256": _digest(label),
        "base_e142_sequence_sha256": _digest(base),
        "candidate_e142_sequence_sha256": _digest(candidate),
        "relation": relation,
        "extension_comparison_count": suffix,
    }


@pytest.fixture(autouse=True)
def isolate_e143_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E143 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e144, "verify_startup_readiness_e143_e142_sequence_prefix_comparison", verify)


def test_e144_replays_deterministically_and_summarizes() -> None:
    records = [
        _comparison("c1", "s0", "s1", "STRICT_PREFIX_EXTENSION", 2),
        _comparison("c2", "s1", "s2", "NOT_PREFIX_EXTENSION"),
        _comparison("c3", "s2", "s3", "IDENTICAL"),
    ]
    first = e144.build_startup_readiness_e144_e143_comparison_sequence(records)
    second = e144.build_startup_readiness_e144_e143_comparison_sequence(records)
    assert first == second
    assert first["comparison_count"] == 3
    assert first["relation_counts"] == {"IDENTICAL": 1, "STRICT_PREFIX_EXTENSION": 1, "NOT_PREFIX_EXTENSION": 1}
    assert first["strict_prefix_extension_suffix_total"] == 2
    assert first["base_e142_sequence_sha256"] == _digest("s0")
    assert first["candidate_e142_sequence_sha256"] == _digest("s3")
    assert e144.verify_startup_readiness_e144_e143_comparison_sequence(first) == first


def test_e144_rejects_minimum_duplicate_and_broken_adjacency() -> None:
    one = _comparison("c1", "s0", "s1")
    with pytest.raises(ValueError, match="at least two"):
        e144.build_startup_readiness_e144_e143_comparison_sequence([one])
    with pytest.raises(ValueError, match="duplicate"):
        e144.build_startup_readiness_e144_e143_comparison_sequence([one, deepcopy(one)])
    with pytest.raises(ValueError, match="adjacency"):
        e144.build_startup_readiness_e144_e143_comparison_sequence([one, _comparison("c2", "wrong", "s2")])


def test_e144_propagates_nested_rejection() -> None:
    rejected = _comparison("c2", "s1", "s2")
    rejected["reject"] = True
    with pytest.raises(ValueError, match="nested E143 rejected"):
        e144.build_startup_readiness_e144_e143_comparison_sequence([_comparison("c1", "s0", "s1"), rejected])


def test_e144_rejects_semantic_forgery_and_malformed_identity() -> None:
    record = e144.build_startup_readiness_e144_e143_comparison_sequence([
        _comparison("c1", "s0", "s1", "STRICT_PREFIX_EXTENSION", 3),
        _comparison("c2", "s1", "s2"),
    ])
    forged = deepcopy(record)
    forged["strict_prefix_extension_suffix_total"] = 999
    with pytest.raises(ValueError, match="suffix"):
        e144.verify_startup_readiness_e144_e143_comparison_sequence(forged)
    malformed = deepcopy(record)
    malformed["comparisons"][0]["comparison_sha256"] = "bad"
    with pytest.raises(ValueError, match="malformed"):
        e144.verify_startup_readiness_e144_e143_comparison_sequence(malformed)


def test_e144_rejects_missing_boundaries_authority_escalation_and_digest_tampering() -> None:
    record = e144.build_startup_readiness_e144_e143_comparison_sequence([
        _comparison("c1", "s0", "s1"), _comparison("c2", "s1", "s2")
    ])
    missing = deepcopy(record)
    missing["truth_boundaries"] = []
    with pytest.raises(ValueError, match="truth boundaries"):
        e144.verify_startup_readiness_e144_e143_comparison_sequence(missing)
    escalated = deepcopy(record)
    escalated["authority"]["automatic_control_allowed"] = True
    with pytest.raises(ValueError, match="authority"):
        e144.verify_startup_readiness_e144_e143_comparison_sequence(escalated)
    tampered = deepcopy(record)
    tampered[e144.E144_DIGEST_FIELD] = _digest("forged")
    with pytest.raises(ValueError, match="digest"):
        e144.verify_startup_readiness_e144_e143_comparison_sequence(tampered)
