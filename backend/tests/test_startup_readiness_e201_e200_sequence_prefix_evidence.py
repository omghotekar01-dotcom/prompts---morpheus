from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e201_e200_sequence_prefix_evidence as e201


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _sequence(label: str, ids: list[str]) -> dict[str, object]:
    return {"sequence_sha256": _digest(label), "comparison_sha256s": [_digest(value) for value in ids]}


@pytest.fixture(autouse=True)
def isolate_e200_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E200 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e201, "verify_startup_readiness_e200_e199_comparison_sequence", verify)


def test_e201_classifies_identical_strict_prefix_and_not_prefix() -> None:
    base = _sequence("base", ["p1", "p2"])
    identical = deepcopy(base)
    strict = _sequence("strict", ["p1", "p2", "p3", "p4"])
    divergent = _sequence("divergent", ["p1", "other"])
    same = e201.build_startup_readiness_e201_e200_sequence_prefix_comparison(base, identical)
    assert same["relation"] == "IDENTICAL"
    assert same["extension_comparison_sha256s"] == []
    extension = e201.build_startup_readiness_e201_e200_sequence_prefix_comparison(base, strict)
    assert extension["relation"] == "STRICT_PREFIX_EXTENSION"
    assert extension["extension_comparison_sha256s"] == [_digest("p3"), _digest("p4")]
    assert extension["extension_comparison_count"] == 2
    other = e201.build_startup_readiness_e201_e200_sequence_prefix_comparison(base, divergent)
    assert other["relation"] == "NOT_PREFIX_EXTENSION"
    assert other["extension_comparison_sha256s"] == []
    assert e201.verify_startup_readiness_e201_e200_sequence_prefix_comparison(extension) == extension


def test_e201_rejects_nested_identity_and_duplicate_failures() -> None:
    base = _sequence("base", ["p1", "p2"])
    with pytest.raises(ValueError, match="nested E200 rejected"):
        e201.build_startup_readiness_e201_e200_sequence_prefix_comparison(base, {"reject": True})
    malformed_sequence = _sequence("candidate", ["p1", "p2"]); malformed_sequence["sequence_sha256"] = "bad"
    with pytest.raises(ValueError, match="valid E200"):
        e201.build_startup_readiness_e201_e200_sequence_prefix_comparison(base, malformed_sequence)
    malformed_ordered = _sequence("candidate", ["p1", "p2"]); malformed_ordered["comparison_sha256s"][1] = "bad"
    with pytest.raises(ValueError, match="valid ordered E199"):
        e201.build_startup_readiness_e201_e200_sequence_prefix_comparison(base, malformed_ordered)
    duplicate = _sequence("candidate", ["p1", "p1"])
    with pytest.raises(ValueError, match="unique ordered E199"):
        e201.build_startup_readiness_e201_e200_sequence_prefix_comparison(base, duplicate)


def test_e201_rejects_relation_suffix_count_boundary_authority_embedded_and_digest_tampering() -> None:
    original = e201.build_startup_readiness_e201_e200_sequence_prefix_comparison(
        _sequence("base", ["p1", "p2"]), _sequence("candidate", ["p1", "p2", "p3"])
    )
    mutations = []
    relation = deepcopy(original); relation["relation"] = "IDENTICAL"; mutations.append(relation)
    suffix = deepcopy(original); suffix["extension_comparison_sha256s"] = []; mutations.append(suffix)
    count = deepcopy(original); count["extension_comparison_count"] = 99; mutations.append(count)
    boundary = deepcopy(original); boundary["truth_boundaries"] = []; mutations.append(boundary)
    authority = deepcopy(original); authority["authority"]["production_deployment_authorized"] = True; mutations.append(authority)
    embedded = deepcopy(original); embedded["candidate_sequence"]["comparison_sha256s"][-1] = _digest("other"); mutations.append(embedded)
    digest = deepcopy(original); digest["comparison_sha256"] = "0" * 64; mutations.append(digest)
    for record in mutations:
        with pytest.raises(ValueError):
            e201.verify_startup_readiness_e201_e200_sequence_prefix_comparison(record)
