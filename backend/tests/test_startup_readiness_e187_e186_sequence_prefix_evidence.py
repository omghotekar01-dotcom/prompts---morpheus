from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e187_e186_sequence_prefix_evidence as e187


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _sequence(label: str, ids: list[str]) -> dict[str, object]:
    return {"sequence_sha256": _digest(label), "comparison_sha256s": [_digest(value) for value in ids]}


@pytest.fixture(autouse=True)
def isolate_e186_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E186 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e187, "verify_startup_readiness_e186_e185_comparison_sequence", verify)


def test_e187_builds_and_replays_all_prefix_relations_deterministically() -> None:
    base = _sequence("s-base", ["c1", "c2"])
    identical = deepcopy(base)
    strict = _sequence("s-strict", ["c1", "c2", "c3", "c4"])
    divergent = _sequence("s-divergent", ["c1", "other"])

    same = e187.build_startup_readiness_e187_e186_sequence_prefix_comparison(base, identical)
    assert same["relation"] == "IDENTICAL"
    assert same["extension_comparison_sha256s"] == []
    assert same["extension_comparison_count"] == 0
    assert e187.verify_startup_readiness_e187_e186_sequence_prefix_comparison(same) == same

    extended = e187.build_startup_readiness_e187_e186_sequence_prefix_comparison(base, strict)
    assert extended["relation"] == "STRICT_PREFIX_EXTENSION"
    assert extended["extension_comparison_sha256s"] == [_digest("c3"), _digest("c4")]
    assert extended["extension_comparison_count"] == 2
    assert e187.verify_startup_readiness_e187_e186_sequence_prefix_comparison(extended) == extended

    not_prefix = e187.build_startup_readiness_e187_e186_sequence_prefix_comparison(base, divergent)
    assert not_prefix["relation"] == "NOT_PREFIX_EXTENSION"
    assert not_prefix["extension_comparison_sha256s"] == []
    assert e187.verify_startup_readiness_e187_e186_sequence_prefix_comparison(not_prefix) == not_prefix


def test_e187_rejects_nested_identity_and_ordered_identity_failures() -> None:
    base = _sequence("base", ["c1", "c2"])
    with pytest.raises(ValueError, match="nested E186 rejected"):
        e187.build_startup_readiness_e187_e186_sequence_prefix_comparison(base, {"reject": True})

    malformed_sequence = _sequence("candidate", ["c1", "c2"])
    malformed_sequence["sequence_sha256"] = "bad"
    with pytest.raises(ValueError, match="valid E186"):
        e187.build_startup_readiness_e187_e186_sequence_prefix_comparison(base, malformed_sequence)

    malformed_ids = _sequence("candidate-ids", ["c1", "c2"])
    malformed_ids["comparison_sha256s"] = [_digest("c1"), "bad"]
    with pytest.raises(ValueError, match="valid ordered E185"):
        e187.build_startup_readiness_e187_e186_sequence_prefix_comparison(base, malformed_ids)

    duplicate_ids = _sequence("candidate-duplicate", ["c1", "c1"])
    with pytest.raises(ValueError, match="unique ordered E185"):
        e187.build_startup_readiness_e187_e186_sequence_prefix_comparison(base, duplicate_ids)


def test_e187_rejects_relation_suffix_count_boundary_authority_embedded_and_digest_tampering() -> None:
    original = e187.build_startup_readiness_e187_e186_sequence_prefix_comparison(
        _sequence("base", ["c1", "c2"]), _sequence("candidate", ["c1", "c2", "c3"])
    )
    mutations = []
    relation = deepcopy(original); relation["relation"] = "UNSUPPORTED"; mutations.append(relation)
    suffix = deepcopy(original); suffix["extension_comparison_sha256s"] = []; mutations.append(suffix)
    count = deepcopy(original); count["extension_comparison_count"] = 99; mutations.append(count)
    boundary = deepcopy(original); boundary["truth_boundaries"] = []; mutations.append(boundary)
    authority = deepcopy(original); authority["authority"]["activation_allowed"] = True; mutations.append(authority)
    embedded = deepcopy(original); embedded["candidate_sequence"]["comparison_sha256s"][-1] = _digest("other"); mutations.append(embedded)
    digest = deepcopy(original); digest["comparison_sha256"] = "0" * 64; mutations.append(digest)
    for record in mutations:
        with pytest.raises(ValueError):
            e187.verify_startup_readiness_e187_e186_sequence_prefix_comparison(record)
