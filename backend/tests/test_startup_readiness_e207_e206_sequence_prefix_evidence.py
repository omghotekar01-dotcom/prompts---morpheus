from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e207_e206_sequence_prefix_evidence as e207


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _sequence(label: str, ids: list[str]) -> dict[str, object]:
    return {"sequence_sha256": _digest(label), "comparison_sha256s": [_digest(value) for value in ids]}


@pytest.fixture(autouse=True)
def isolate_e206_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E206 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e207, "verify_startup_readiness_e206_e205_comparison_sequence", verify)


def test_e207_derives_all_prefix_relations_and_replays() -> None:
    base = _sequence("s1", ["p1", "p2"])
    identical = e207.build_startup_readiness_e207_e206_sequence_prefix_comparison(base, deepcopy(base))
    assert identical["relation"] == "IDENTICAL"
    assert identical["extension_comparison_sha256s"] == []
    extension = e207.build_startup_readiness_e207_e206_sequence_prefix_comparison(base, _sequence("s2", ["p1", "p2", "p3"]))
    assert extension["relation"] == "STRICT_PREFIX_EXTENSION"
    assert extension["extension_comparison_sha256s"] == [_digest("p3")]
    assert extension["extension_comparison_count"] == 1
    nonprefix = e207.build_startup_readiness_e207_e206_sequence_prefix_comparison(base, _sequence("s3", ["p1", "other"]))
    assert nonprefix["relation"] == "NOT_PREFIX_EXTENSION"
    assert nonprefix["extension_comparison_sha256s"] == []
    assert e207.verify_startup_readiness_e207_e206_sequence_prefix_comparison(extension) == extension


def test_e207_rejects_nested_identity_and_order_failures() -> None:
    base = _sequence("s1", ["p1", "p2"])
    with pytest.raises(ValueError, match="nested E206 rejected"):
        e207.build_startup_readiness_e207_e206_sequence_prefix_comparison(base, {"reject": True})
    malformed_sequence = _sequence("s2", ["p1", "p2"]); malformed_sequence["sequence_sha256"] = "bad"
    with pytest.raises(ValueError, match="valid E206"):
        e207.build_startup_readiness_e207_e206_sequence_prefix_comparison(base, malformed_sequence)
    malformed_order = _sequence("s2", ["p1", "p2"]); malformed_order["comparison_sha256s"] = [_digest("p1"), "bad"]
    with pytest.raises(ValueError, match="valid ordered E205"):
        e207.build_startup_readiness_e207_e206_sequence_prefix_comparison(base, malformed_order)
    duplicate = _sequence("s2", ["p1", "p1"])
    with pytest.raises(ValueError, match="unique ordered E205"):
        e207.build_startup_readiness_e207_e206_sequence_prefix_comparison(base, duplicate)


def test_e207_rejects_relation_suffix_count_boundary_authority_embedded_and_digest_tampering() -> None:
    original = e207.build_startup_readiness_e207_e206_sequence_prefix_comparison(
        _sequence("s1", ["p1", "p2"]), _sequence("s2", ["p1", "p2", "p3"])
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
            e207.verify_startup_readiness_e207_e206_sequence_prefix_comparison(record)
