from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e142_e141_comparison_sequence_evidence as e142


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _comparison(label: str, base: str, candidate: str, relation: str = "IDENTICAL", suffix: int = 0) -> dict[str, object]:
    return {
        "comparison_sha256": _digest(label),
        "base_e140_sequence_sha256": _digest(base),
        "candidate_e140_sequence_sha256": _digest(candidate),
        "relation": relation,
        "extension_comparison_count": suffix,
    }


@pytest.fixture(autouse=True)
def isolate_e141_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E141 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e142, "verify_startup_readiness_e141_e140_sequence_prefix_comparison", verify)


def _records() -> list[dict[str, object]]:
    return [
        _comparison("c1", "s0", "s1", "STRICT_PREFIX_EXTENSION", 2),
        _comparison("c2", "s1", "s2", "NOT_PREFIX_EXTENSION"),
        _comparison("c3", "s2", "s3", "IDENTICAL"),
    ]


def test_e142_replays_deterministically_and_summarizes_relations() -> None:
    first = e142.build_startup_readiness_e142_e141_comparison_sequence(_records())
    second = e142.build_startup_readiness_e142_e141_comparison_sequence(_records())
    assert first == second
    assert first["comparison_count"] == 3
    assert first["relation_counts"] == {"IDENTICAL": 1, "STRICT_PREFIX_EXTENSION": 1, "NOT_PREFIX_EXTENSION": 1}
    assert first["strict_prefix_suffix_comparison_count"] == 2
    assert e142.verify_startup_readiness_e142_e141_comparison_sequence(first) == first


def test_e142_requires_two_records_and_rejects_duplicates_and_broken_adjacency() -> None:
    with pytest.raises(ValueError):
        e142.build_startup_readiness_e142_e141_comparison_sequence(_records()[:1])
    duplicate = _records()[:2]
    duplicate[1]["comparison_sha256"] = duplicate[0]["comparison_sha256"]
    with pytest.raises(ValueError, match="duplicate"):
        e142.build_startup_readiness_e142_e141_comparison_sequence(duplicate)
    broken = _records()[:2]
    broken[1]["base_e140_sequence_sha256"] = _digest("wrong")
    with pytest.raises(ValueError, match="adjacency"):
        e142.build_startup_readiness_e142_e141_comparison_sequence(broken)


def test_e142_propagates_nested_rejection() -> None:
    records = _records()[:2]
    records[1]["reject"] = True
    with pytest.raises(ValueError, match="nested E141 rejected"):
        e142.build_startup_readiness_e142_e141_comparison_sequence(records)


def test_e142_rejects_semantic_forgery_malformed_identity_and_authority_escalation() -> None:
    record = e142.build_startup_readiness_e142_e141_comparison_sequence(_records())
    forged = deepcopy(record)
    forged["relation_counts"]["IDENTICAL"] = 9
    with pytest.raises(ValueError, match="relation_counts"):
        e142.verify_startup_readiness_e142_e141_comparison_sequence(forged)
    malformed = deepcopy(record)
    malformed["comparison_sha256s"][0] = "bad"
    with pytest.raises(ValueError):
        e142.verify_startup_readiness_e142_e141_comparison_sequence(malformed)
    escalated = deepcopy(record)
    escalated["authority"]["automatic_control_allowed"] = True
    with pytest.raises(ValueError, match="authority"):
        e142.verify_startup_readiness_e142_e141_comparison_sequence(escalated)


def test_e142_rejects_missing_truth_boundaries_and_digest_tampering() -> None:
    record = e142.build_startup_readiness_e142_e141_comparison_sequence(_records())
    missing = deepcopy(record)
    missing["truth_boundaries"] = []
    with pytest.raises(ValueError, match="truth boundaries"):
        e142.verify_startup_readiness_e142_e141_comparison_sequence(missing)
    tampered = deepcopy(record)
    tampered[e142.E142_DIGEST_FIELD] = _digest("forged")
    with pytest.raises(ValueError, match="digest"):
        e142.verify_startup_readiness_e142_e141_comparison_sequence(tampered)
