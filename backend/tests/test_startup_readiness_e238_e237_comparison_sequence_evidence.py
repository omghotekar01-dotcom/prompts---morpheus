from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e238_e237_comparison_sequence_evidence as e238


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _comparison(label: str, base: str, candidate: str, relation: str = "IDENTICAL", suffix: list[str] | None = None) -> dict[str, object]:
    suffix_ids = [_digest(value) for value in (suffix or [])]
    return {
        "comparison_sha256": _digest(label),
        "base_e236_sequence_sha256": _digest(base),
        "candidate_e236_sequence_sha256": _digest(candidate),
        "relation": relation,
        "extension_comparison_sha256s": suffix_ids,
        "extension_comparison_count": len(suffix_ids),
    }


@pytest.fixture(autouse=True)
def isolate_e237_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E237 rejected")
        return deepcopy(record)

    monkeypatch.setattr(
        e238,
        "verify_startup_readiness_e237_e236_sequence_prefix_comparison",
        verify,
    )


def test_e238_derives_relation_counts_suffix_total_endpoints_and_zero_authority() -> None:
    comparisons = [
        _comparison("c1", "s1", "s2"),
        _comparison("c2", "s2", "s3", "STRICT_PREFIX_EXTENSION", ["p1", "p2"]),
        _comparison("c3", "s3", "s4", "NOT_PREFIX_EXTENSION"),
    ]
    record = e238.build_startup_readiness_e238_e237_comparison_sequence(comparisons)

    assert record["comparison_count"] == 3
    assert record["relation_counts"] == {
        "IDENTICAL": 1,
        "STRICT_PREFIX_EXTENSION": 1,
        "NOT_PREFIX_EXTENSION": 1,
    }
    assert record["strict_prefix_extension_e235_suffix_total"] == 2
    assert record["start_e236_sequence_sha256"] == _digest("s1")
    assert record["end_e236_sequence_sha256"] == _digest("s4")
    assert record["authority"] == {
        "production_deployment_authorized": False,
        "automatic_control_allowed": False,
        "activation_allowed": False,
    }
    assert e238.verify_startup_readiness_e238_e237_comparison_sequence(record) == record


def test_e238_rejects_short_nested_malformed_duplicate_and_broken_adjacency() -> None:
    with pytest.raises(ValueError, match="at least two"):
        e238.build_startup_readiness_e238_e237_comparison_sequence([_comparison("c1", "s1", "s2")])

    with pytest.raises(ValueError, match="nested E237 rejected"):
        e238.build_startup_readiness_e238_e237_comparison_sequence([
            _comparison("c1", "s1", "s2"),
            {"reject": True},
        ])

    malformed = _comparison("c1", "s1", "s2")
    malformed["comparison_sha256"] = "bad"
    with pytest.raises(ValueError, match="valid E237"):
        e238.build_startup_readiness_e238_e237_comparison_sequence([
            malformed,
            _comparison("c2", "s2", "s3"),
        ])

    duplicate = _comparison("same", "s1", "s2")
    duplicate2 = _comparison("same", "s2", "s3")
    with pytest.raises(ValueError, match="unique E237"):
        e238.build_startup_readiness_e238_e237_comparison_sequence([duplicate, duplicate2])

    with pytest.raises(ValueError, match="adjacency"):
        e238.build_startup_readiness_e238_e237_comparison_sequence([
            _comparison("c1", "s1", "s2"),
            _comparison("c2", "other", "s3"),
        ])


def test_e238_rejects_unsupported_relation_and_inconsistent_suffix_semantics() -> None:
    unsupported = _comparison("c1", "s1", "s2")
    unsupported["relation"] = "NEWER"
    with pytest.raises(ValueError, match="unsupported E237 relation"):
        e238.build_startup_readiness_e238_e237_comparison_sequence([
            unsupported,
            _comparison("c2", "s2", "s3"),
        ])

    wrong_count = _comparison("c1", "s1", "s2", "STRICT_PREFIX_EXTENSION", ["p1"])
    wrong_count["extension_comparison_count"] = 2
    with pytest.raises(ValueError, match="consistent E237 suffix semantics"):
        e238.build_startup_readiness_e238_e237_comparison_sequence([
            wrong_count,
            _comparison("c2", "s2", "s3"),
        ])

    illegal_suffix = _comparison("c1", "s1", "s2", "IDENTICAL", ["p1"])
    with pytest.raises(ValueError, match="only for strict-prefix"):
        e238.build_startup_readiness_e238_e237_comparison_sequence([
            illegal_suffix,
            _comparison("c2", "s2", "s3"),
        ])


def test_e238_rejects_summary_suffix_endpoint_boundary_authority_embedded_and_digest_tampering() -> None:
    original = e238.build_startup_readiness_e238_e237_comparison_sequence([
        _comparison("c1", "s1", "s2", "STRICT_PREFIX_EXTENSION", ["p1"]),
        _comparison("c2", "s2", "s3"),
    ])

    mutations = []
    summary = deepcopy(original); summary["relation_counts"]["IDENTICAL"] = 9; mutations.append(summary)
    suffix = deepcopy(original); suffix["strict_prefix_extension_e235_suffix_total"] = 0; mutations.append(suffix)
    endpoint = deepcopy(original); endpoint["end_e236_sequence_sha256"] = _digest("other"); mutations.append(endpoint)
    boundary = deepcopy(original); boundary["truth_boundaries"] = []; mutations.append(boundary)
    authority = deepcopy(original); authority["authority"]["activation_allowed"] = True; mutations.append(authority)
    embedded = deepcopy(original); embedded["comparisons"][1]["candidate_e236_sequence_sha256"] = _digest("other"); mutations.append(embedded)
    digest = deepcopy(original); digest["sequence_sha256"] = "0" * 64; mutations.append(digest)

    for record in mutations:
        with pytest.raises(ValueError):
            e238.verify_startup_readiness_e238_e237_comparison_sequence(record)
