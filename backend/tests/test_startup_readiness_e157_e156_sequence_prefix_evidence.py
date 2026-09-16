from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e157_e156_sequence_prefix_evidence as e157


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _sequence(label: str, ids: list[str]) -> dict[str, object]:
    return {"sequence_sha256": _digest(label), "comparison_sha256s": [_digest(value) for value in ids]}


@pytest.fixture(autouse=True)
def isolate_e156_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E156 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e157, "verify_startup_readiness_e156_e155_comparison_sequence", verify)


def test_e157_classifies_identical_and_replays_deterministically() -> None:
    base = _sequence("s1", ["c1", "c2"])
    candidate = _sequence("s2", ["c1", "c2"])
    first = e157.build_startup_readiness_e157_e156_sequence_prefix_comparison(base, candidate)
    second = e157.build_startup_readiness_e157_e156_sequence_prefix_comparison(deepcopy(base), deepcopy(candidate))
    assert first == second
    assert first["relation"] == "IDENTICAL"
    assert first["extension_comparison_sha256s"] == []
    assert first["extension_comparison_count"] == 0
    assert e157.verify_startup_readiness_e157_e156_sequence_prefix_comparison(first) == first


def test_e157_classifies_strict_prefix_and_discloses_exact_suffix() -> None:
    base = _sequence("s1", ["c1", "c2"])
    candidate = _sequence("s2", ["c1", "c2", "c3", "c4"])
    record = e157.build_startup_readiness_e157_e156_sequence_prefix_comparison(base, candidate)
    assert record["relation"] == "STRICT_PREFIX_EXTENSION"
    assert record["extension_comparison_sha256s"] == [_digest("c3"), _digest("c4")]
    assert record["extension_comparison_count"] == 2


def test_e157_classifies_non_prefix_without_suffix_disclosure() -> None:
    record = e157.build_startup_readiness_e157_e156_sequence_prefix_comparison(
        _sequence("s1", ["c1", "c2"]), _sequence("s2", ["c1", "other", "c3"])
    )
    assert record["relation"] == "NOT_PREFIX_EXTENSION"
    assert record["extension_comparison_sha256s"] == []
    assert record["extension_comparison_count"] == 0


def test_e157_rejects_nested_and_malformed_identity_evidence() -> None:
    with pytest.raises(ValueError, match="nested E156 rejected"):
        e157.build_startup_readiness_e157_e156_sequence_prefix_comparison({"reject": True}, _sequence("s2", ["c1"]))
    malformed = _sequence("s1", ["c1"]); malformed["sequence_sha256"] = "bad"
    with pytest.raises(ValueError, match="valid E156"):
        e157.build_startup_readiness_e157_e156_sequence_prefix_comparison(malformed, _sequence("s2", ["c1"]))
    malformed_ids = _sequence("s1", ["c1"]); malformed_ids["comparison_sha256s"] = ["bad"]
    with pytest.raises(ValueError, match="exact ordered E155"):
        e157.build_startup_readiness_e157_e156_sequence_prefix_comparison(malformed_ids, _sequence("s2", ["c1"]))


@pytest.mark.parametrize("field,value", [
    ("relation", "STRICT_PREFIX_EXTENSION"),
    ("extension_comparison_sha256s", ["0" * 64]),
    ("extension_comparison_count", 99),
    ("base_e156_sequence_sha256", "0" * 64),
])
def test_e157_rejects_semantic_forgery(field: str, value: object) -> None:
    record = e157.build_startup_readiness_e157_e156_sequence_prefix_comparison(
        _sequence("s1", ["c1", "c2"]), _sequence("s2", ["c1", "c2"])
    )
    record[field] = value
    with pytest.raises(ValueError):
        e157.verify_startup_readiness_e157_e156_sequence_prefix_comparison(record)


def test_e157_rejects_boundary_authority_embedded_and_digest_tampering() -> None:
    original = e157.build_startup_readiness_e157_e156_sequence_prefix_comparison(
        _sequence("s1", ["c1", "c2"]), _sequence("s2", ["c1", "c2", "c3"])
    )
    mutations = []
    no_boundary = deepcopy(original); no_boundary["truth_boundaries"] = []; mutations.append(no_boundary)
    authority = deepcopy(original); authority["authority"]["activation_allowed"] = True; mutations.append(authority)
    embedded = deepcopy(original); embedded["candidate_sequence"]["comparison_sha256s"] = [_digest("other")]; mutations.append(embedded)
    digest = deepcopy(original); digest["comparison_sha256"] = "0" * 64; mutations.append(digest)
    for record in mutations:
        with pytest.raises(ValueError):
            e157.verify_startup_readiness_e157_e156_sequence_prefix_comparison(record)
