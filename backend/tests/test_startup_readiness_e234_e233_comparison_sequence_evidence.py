from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e234_e233_comparison_sequence_evidence as e234


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _comparison(
    label: str,
    base: str,
    candidate: str,
    relation: str = "IDENTICAL",
    suffix: list[str] | None = None,
) -> dict[str, object]:
    suffix_ids = [_digest(value) for value in (suffix or [])]
    return {
        "comparison_sha256": _digest(label),
        "base_e232_sequence_sha256": _digest(base),
        "candidate_e232_sequence_sha256": _digest(candidate),
        "relation": relation,
        "extension_comparison_sha256s": suffix_ids,
        "extension_comparison_count": len(suffix_ids),
    }


@pytest.fixture(autouse=True)
def isolate_e233_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E233 rejected")
        return deepcopy(record)

    monkeypatch.setattr(
        e234,
        "verify_startup_readiness_e233_e232_sequence_prefix_comparison",
        verify,
    )


def test_e234_replays_ordered_sequence_and_derives_summaries_and_endpoints() -> None:
    first = _comparison("p1", "s1", "s2")
    second = _comparison("p2", "s2", "s3", "STRICT_PREFIX_EXTENSION", ["c3", "c4"])
    third = _comparison("p3", "s3", "s4", "NOT_PREFIX_EXTENSION")

    record = e234.build_startup_readiness_e234_e233_comparison_sequence([first, second, third])

    assert record["comparison_sha256s"] == [_digest("p1"), _digest("p2"), _digest("p3")]
    assert record["comparison_count"] == 3
    assert record["start_e232_sequence_sha256"] == _digest("s1")
    assert record["end_e232_sequence_sha256"] == _digest("s4")
    assert record["relation_counts"] == {
        "IDENTICAL": 1,
        "STRICT_PREFIX_EXTENSION": 1,
        "NOT_PREFIX_EXTENSION": 1,
    }
    assert record["strict_prefix_extension_e231_suffix_total"] == 2
    assert record["authority"] == {
        "production_deployment_authorized": False,
        "automatic_control_allowed": False,
        "activation_allowed": False,
    }
    assert e234.verify_startup_readiness_e234_e233_comparison_sequence(record) == record


def test_e234_rejects_short_nested_malformed_duplicate_and_broken_adjacency() -> None:
    first = _comparison("p1", "s1", "s2")
    second = _comparison("p2", "s2", "s3")

    with pytest.raises(ValueError, match="at least two"):
        e234.build_startup_readiness_e234_e233_comparison_sequence([first])
    with pytest.raises(ValueError, match="nested E233 rejected"):
        e234.build_startup_readiness_e234_e233_comparison_sequence([first, {"reject": True}])

    malformed = deepcopy(second); malformed["comparison_sha256"] = "bad"
    with pytest.raises(ValueError, match="valid E233"):
        e234.build_startup_readiness_e234_e233_comparison_sequence([first, malformed])

    duplicate = deepcopy(first)
    duplicate["base_e232_sequence_sha256"] = _digest("s2")
    duplicate["candidate_e232_sequence_sha256"] = _digest("s3")
    with pytest.raises(ValueError, match="unique E233"):
        e234.build_startup_readiness_e234_e233_comparison_sequence([first, duplicate])

    broken = _comparison("p2", "other", "s3")
    with pytest.raises(ValueError, match="adjacency"):
        e234.build_startup_readiness_e234_e233_comparison_sequence([first, broken])


def test_e234_rejects_relation_and_suffix_semantic_violations() -> None:
    first = _comparison("p1", "s1", "s2")
    unsupported = _comparison("p2", "s2", "s3", "UNKNOWN")
    with pytest.raises(ValueError, match="unsupported"):
        e234.build_startup_readiness_e234_e233_comparison_sequence([first, unsupported])

    suffix_on_identical = _comparison("p2", "s2", "s3", "IDENTICAL", ["c3"])
    with pytest.raises(ValueError, match="strict-prefix"):
        e234.build_startup_readiness_e234_e233_comparison_sequence([first, suffix_on_identical])

    inconsistent = _comparison("p2", "s2", "s3", "STRICT_PREFIX_EXTENSION", ["c3"])
    inconsistent["extension_comparison_count"] = 9
    with pytest.raises(ValueError, match="consistent"):
        e234.build_startup_readiness_e234_e233_comparison_sequence([first, inconsistent])


def test_e234_fails_closed_on_summary_endpoint_boundary_authority_embedded_and_digest_tampering() -> None:
    first = _comparison("p1", "s1", "s2")
    second = _comparison("p2", "s2", "s3", "STRICT_PREFIX_EXTENSION", ["c3"])
    original = e234.build_startup_readiness_e234_e233_comparison_sequence([first, second])

    mutations = []
    summary = deepcopy(original); summary["relation_counts"]["IDENTICAL"] = 9; mutations.append(summary)
    suffix_total = deepcopy(original); suffix_total["strict_prefix_extension_e231_suffix_total"] = 0; mutations.append(suffix_total)
    endpoint = deepcopy(original); endpoint["end_e232_sequence_sha256"] = _digest("other"); mutations.append(endpoint)
    boundary = deepcopy(original); boundary["truth_boundaries"] = []; mutations.append(boundary)
    authority = deepcopy(original); authority["authority"]["activation_allowed"] = True; mutations.append(authority)
    embedded = deepcopy(original); embedded["comparisons"][1]["candidate_e232_sequence_sha256"] = _digest("other"); mutations.append(embedded)
    digest = deepcopy(original); digest["sequence_sha256"] = "0" * 64; mutations.append(digest)

    for record in mutations:
        with pytest.raises(ValueError):
            e234.verify_startup_readiness_e234_e233_comparison_sequence(record)
