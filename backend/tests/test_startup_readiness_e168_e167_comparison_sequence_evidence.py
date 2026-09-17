from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e168_e167_comparison_sequence_evidence as e168


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _comparison(label: str, base: str, candidate: str, relation: str = "IDENTICAL", suffix: list[str] | None = None) -> dict[str, object]:
    suffix_ids = [_digest(value) for value in (suffix or [])]
    return {
        "comparison_sha256": _digest(label),
        "base_e166_sequence_sha256": _digest(base),
        "candidate_e166_sequence_sha256": _digest(candidate),
        "relation": relation,
        "extension_comparison_sha256s": suffix_ids,
        "extension_comparison_count": len(suffix_ids),
    }


@pytest.fixture(autouse=True)
def isolate_e167_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E167 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e168, "verify_startup_readiness_e167_e166_sequence_prefix_comparison", verify)


def test_e168_builds_replays_summarizes_and_binds_endpoints_deterministically() -> None:
    first = _comparison("cmp1", "s1", "s2", "STRICT_PREFIX_EXTENSION", ["x", "y"])
    second = _comparison("cmp2", "s2", "s3", "NOT_PREFIX_EXTENSION")
    record = e168.build_startup_readiness_e168_e167_comparison_sequence([first, second])
    assert record["comparison_sha256s"] == [_digest("cmp1"), _digest("cmp2")]
    assert record["comparison_count"] == 2
    assert record["start_e166_sequence_sha256"] == _digest("s1")
    assert record["end_e166_sequence_sha256"] == _digest("s3")
    assert record["relation_counts"] == {"IDENTICAL": 0, "STRICT_PREFIX_EXTENSION": 1, "NOT_PREFIX_EXTENSION": 1}
    assert record["strict_prefix_extension_e165_suffix_total"] == 2
    assert record["authority"] == {"production_deployment_authorized": False, "automatic_control_allowed": False, "activation_allowed": False}
    assert e168.verify_startup_readiness_e168_e167_comparison_sequence(record) == record
    assert e168.build_startup_readiness_e168_e167_comparison_sequence([first, second]) == record


def test_e168_rejects_short_nested_malformed_duplicate_and_broken_adjacency() -> None:
    first = _comparison("cmp1", "s1", "s2")
    second = _comparison("cmp2", "s2", "s3")
    with pytest.raises(ValueError):
        e168.build_startup_readiness_e168_e167_comparison_sequence([first])
    rejected = deepcopy(second); rejected["reject"] = True
    with pytest.raises(ValueError):
        e168.build_startup_readiness_e168_e167_comparison_sequence([first, rejected])
    malformed = deepcopy(second); malformed["comparison_sha256"] = "bad"
    with pytest.raises(ValueError):
        e168.build_startup_readiness_e168_e167_comparison_sequence([first, malformed])
    duplicate = deepcopy(second); duplicate["comparison_sha256"] = first["comparison_sha256"]
    with pytest.raises(ValueError):
        e168.build_startup_readiness_e168_e167_comparison_sequence([first, duplicate])
    broken = deepcopy(second); broken["base_e166_sequence_sha256"] = _digest("other")
    with pytest.raises(ValueError):
        e168.build_startup_readiness_e168_e167_comparison_sequence([first, broken])


def test_e168_rejects_inconsistent_relation_and_suffix_semantics() -> None:
    first = _comparison("cmp1", "s1", "s2")
    bad_relation = _comparison("cmp2", "s2", "s3", "UNKNOWN")
    with pytest.raises(ValueError):
        e168.build_startup_readiness_e168_e167_comparison_sequence([first, bad_relation])
    illegal_suffix = _comparison("cmp2", "s2", "s3", "IDENTICAL", ["x"])
    with pytest.raises(ValueError):
        e168.build_startup_readiness_e168_e167_comparison_sequence([first, illegal_suffix])
    mismatch = _comparison("cmp2", "s2", "s3", "STRICT_PREFIX_EXTENSION", ["x"]); mismatch["extension_comparison_count"] = 2
    with pytest.raises(ValueError):
        e168.build_startup_readiness_e168_e167_comparison_sequence([first, mismatch])


@pytest.mark.parametrize("field", ["comparison_count", "start_e166_sequence_sha256", "end_e166_sequence_sha256", "relation_counts", "strict_prefix_extension_e165_suffix_total", "truth_boundaries", "authority", "sequence_sha256"])
def test_e168_replay_rejects_summary_boundary_authority_and_digest_tampering(field: str) -> None:
    record = e168.build_startup_readiness_e168_e167_comparison_sequence([
        _comparison("cmp1", "s1", "s2", "STRICT_PREFIX_EXTENSION", ["x"]),
        _comparison("cmp2", "s2", "s3"),
    ])
    tampered = deepcopy(record)
    if field in {"comparison_count", "strict_prefix_extension_e165_suffix_total"}:
        tampered[field] += 1
    elif field in {"start_e166_sequence_sha256", "end_e166_sequence_sha256", "sequence_sha256"}:
        tampered[field] = _digest("tampered")
    elif field == "relation_counts":
        tampered[field]["IDENTICAL"] += 1
    elif field == "truth_boundaries":
        tampered[field] = tampered[field][:-1]
    else:
        tampered[field]["production_deployment_authorized"] = True
    with pytest.raises(ValueError):
        e168.verify_startup_readiness_e168_e167_comparison_sequence(tampered)


def test_e168_replay_rejects_embedded_comparison_tampering() -> None:
    record = e168.build_startup_readiness_e168_e167_comparison_sequence([_comparison("cmp1", "s1", "s2"), _comparison("cmp2", "s2", "s3")])
    tampered = deepcopy(record)
    tampered["comparisons"][1]["candidate_e166_sequence_sha256"] = _digest("forged")
    with pytest.raises(ValueError):
        e168.verify_startup_readiness_e168_e167_comparison_sequence(tampered)
