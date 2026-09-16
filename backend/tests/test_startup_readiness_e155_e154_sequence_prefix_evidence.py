from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e155_e154_sequence_prefix_evidence as e155


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _sequence(label: str, ids: list[str]) -> dict[str, object]:
    return {"sequence_sha256": _digest(label), "comparison_sha256s": [_digest(value) for value in ids]}


@pytest.fixture(autouse=True)
def isolate_e154_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E154 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e155, "verify_startup_readiness_e154_e153_comparison_sequence", verify)


@pytest.mark.parametrize(
    "base_ids,candidate_ids,relation,suffix",
    [
        (["c1", "c2"], ["c1", "c2"], "IDENTICAL", []),
        (["c1", "c2"], ["c1", "c2", "c3"], "STRICT_PREFIX_EXTENSION", ["c3"]),
        (["c1", "c2"], ["c1", "other"], "NOT_PREFIX_EXTENSION", []),
    ],
)
def test_e155_classifies_prefix_relation_deterministically(base_ids: list[str], candidate_ids: list[str], relation: str, suffix: list[str]) -> None:
    base = _sequence("base", base_ids)
    candidate = _sequence("candidate", candidate_ids)
    first = e155.build_startup_readiness_e155_e154_sequence_prefix_comparison(base, candidate)
    second = e155.build_startup_readiness_e155_e154_sequence_prefix_comparison(deepcopy(base), deepcopy(candidate))
    assert first == second
    assert first["relation"] == relation
    assert first["extension_comparison_sha256s"] == [_digest(value) for value in suffix]
    assert first["extension_comparison_count"] == len(suffix)
    assert e155.verify_startup_readiness_e155_e154_sequence_prefix_comparison(first) == first


def test_e155_rejects_nested_and_malformed_identities() -> None:
    valid = _sequence("valid", ["c1", "c2"])
    with pytest.raises(ValueError, match="nested E154 rejected"):
        e155.build_startup_readiness_e155_e154_sequence_prefix_comparison({"reject": True}, valid)
    malformed_sequence = _sequence("bad", ["c1"]); malformed_sequence["sequence_sha256"] = "bad"
    with pytest.raises(ValueError, match="valid E154 sequence identities"):
        e155.build_startup_readiness_e155_e154_sequence_prefix_comparison(malformed_sequence, valid)
    malformed_comparison = _sequence("bad-comparison", ["c1"]); malformed_comparison["comparison_sha256s"] = ["bad"]
    with pytest.raises(ValueError, match="exact ordered E153"):
        e155.build_startup_readiness_e155_e154_sequence_prefix_comparison(valid, malformed_comparison)


@pytest.mark.parametrize("field,value", [
    ("relation", "IDENTICAL"),
    ("extension_comparison_sha256s", []),
    ("extension_comparison_count", 0),
    ("base_e154_sequence_sha256", "0" * 64),
])
def test_e155_rejects_relation_suffix_and_identity_forgery(field: str, value: object) -> None:
    record = e155.build_startup_readiness_e155_e154_sequence_prefix_comparison(
        _sequence("base", ["c1", "c2"]), _sequence("candidate", ["c1", "c2", "c3"])
    )
    record[field] = value
    with pytest.raises(ValueError):
        e155.verify_startup_readiness_e155_e154_sequence_prefix_comparison(record)


def test_e155_rejects_boundary_authority_and_digest_tampering() -> None:
    original = e155.build_startup_readiness_e155_e154_sequence_prefix_comparison(
        _sequence("base", ["c1", "c2"]), _sequence("candidate", ["c1", "c2", "c3"])
    )
    mutations = []
    no_boundary = deepcopy(original); no_boundary["truth_boundaries"] = []; mutations.append(no_boundary)
    authority = deepcopy(original); authority["authority"]["activation_allowed"] = True; mutations.append(authority)
    digest = deepcopy(original); digest["comparison_sha256"] = "0" * 64; mutations.append(digest)
    embedded = deepcopy(original); embedded["candidate_sequence"]["comparison_sha256s"].append(_digest("c4")); mutations.append(embedded)
    for record in mutations:
        with pytest.raises(ValueError):
            e155.verify_startup_readiness_e155_e154_sequence_prefix_comparison(record)
