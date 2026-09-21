from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e215_e214_sequence_prefix_evidence as e215


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _sequence(label: str, ids: list[str]) -> dict[str, object]:
    return {
        "sequence_sha256": _digest(label),
        "comparison_sha256s": [_digest(value) for value in ids],
    }


@pytest.fixture(autouse=True)
def isolate_e214_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E214 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e215, "verify_startup_readiness_e214_e213_comparison_sequence", verify)


def test_e215_classifies_identical_strict_prefix_and_non_prefix() -> None:
    base = _sequence("s1", ["p1", "p2"])
    identical = _sequence("s2", ["p1", "p2"])
    extension = _sequence("s3", ["p1", "p2", "p3", "p4"])
    divergent = _sequence("s4", ["p1", "other"])
    same = e215.build_startup_readiness_e215_e214_sequence_prefix_comparison(base, identical)
    assert same["relation"] == "IDENTICAL"
    assert same["extension_comparison_sha256s"] == []
    strict = e215.build_startup_readiness_e215_e214_sequence_prefix_comparison(base, extension)
    assert strict["relation"] == "STRICT_PREFIX_EXTENSION"
    assert strict["extension_comparison_sha256s"] == [_digest("p3"), _digest("p4")]
    assert strict["extension_comparison_count"] == 2
    nonprefix = e215.build_startup_readiness_e215_e214_sequence_prefix_comparison(base, divergent)
    assert nonprefix["relation"] == "NOT_PREFIX_EXTENSION"
    assert nonprefix["extension_comparison_sha256s"] == []
    assert e215.verify_startup_readiness_e215_e214_sequence_prefix_comparison(strict) == strict


def test_e215_rejects_nested_identity_and_ordered_identity_failures() -> None:
    base = _sequence("s1", ["p1", "p2"])
    with pytest.raises(ValueError, match="nested E214 rejected"):
        e215.build_startup_readiness_e215_e214_sequence_prefix_comparison(base, {"reject": True})
    malformed_identity = _sequence("s2", ["p1", "p2"]); malformed_identity["sequence_sha256"] = "bad"
    with pytest.raises(ValueError, match="valid E214"):
        e215.build_startup_readiness_e215_e214_sequence_prefix_comparison(base, malformed_identity)
    malformed_ids = _sequence("s2", ["p1", "p2"]); malformed_ids["comparison_sha256s"] = ["bad", _digest("p2")]
    with pytest.raises(ValueError, match="valid ordered E213"):
        e215.build_startup_readiness_e215_e214_sequence_prefix_comparison(base, malformed_ids)
    duplicate_ids = _sequence("s2", ["p1", "p1"])
    with pytest.raises(ValueError, match="unique ordered E213"):
        e215.build_startup_readiness_e215_e214_sequence_prefix_comparison(base, duplicate_ids)


def test_e215_rejects_relation_suffix_count_boundary_authority_embedded_and_digest_tampering() -> None:
    original = e215.build_startup_readiness_e215_e214_sequence_prefix_comparison(
        _sequence("s1", ["p1", "p2"]), _sequence("s2", ["p1", "p2", "p3"])
    )
    mutations = []
    relation = deepcopy(original); relation["relation"] = "IDENTICAL"; mutations.append(relation)
    suffix = deepcopy(original); suffix["extension_comparison_sha256s"] = []; mutations.append(suffix)
    count = deepcopy(original); count["extension_comparison_count"] = 99; mutations.append(count)
    boundary = deepcopy(original); boundary["truth_boundaries"] = []; mutations.append(boundary)
    authority = deepcopy(original); authority["authority"]["activation_allowed"] = True; mutations.append(authority)
    embedded = deepcopy(original); embedded["candidate_sequence"]["comparison_sha256s"][-1] = _digest("other"); mutations.append(embedded)
    digest = deepcopy(original); digest["comparison_sha256"] = "0" * 64; mutations.append(digest)
    for record in mutations:
        with pytest.raises(ValueError):
            e215.verify_startup_readiness_e215_e214_sequence_prefix_comparison(record)
