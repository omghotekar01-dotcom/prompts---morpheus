from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e147_e146_sequence_prefix_evidence as e147


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _sequence(label: str, comparisons: list[str]) -> dict[str, object]:
    return {"sequence_sha256": _digest(label), "comparison_sha256s": [_digest(item) for item in comparisons]}


@pytest.fixture(autouse=True)
def isolate_e146_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E146 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e147, "verify_startup_readiness_e146_e145_comparison_sequence", verify)


def test_e147_identical_replays_deterministically() -> None:
    base = _sequence("s1", ["a", "b"])
    first = e147.build_startup_readiness_e147_e146_sequence_prefix_comparison(base, deepcopy(base))
    second = e147.build_startup_readiness_e147_e146_sequence_prefix_comparison(base, deepcopy(base))
    assert first == second
    assert first["relation"] == "IDENTICAL"
    assert first["extension_comparison_sha256s"] == []
    assert e147.verify_startup_readiness_e147_e146_sequence_prefix_comparison(first) == first


def test_e147_strict_prefix_exposes_exact_suffix() -> None:
    record = e147.build_startup_readiness_e147_e146_sequence_prefix_comparison(
        _sequence("base", ["a", "b"]), _sequence("candidate", ["a", "b", "c", "d"])
    )
    assert record["relation"] == "STRICT_PREFIX_EXTENSION"
    assert record["extension_comparison_sha256s"] == [_digest("c"), _digest("d")]
    assert record["extension_comparison_count"] == 2


def test_e147_divergent_and_reverse_prefix_are_not_extensions() -> None:
    divergent = e147.build_startup_readiness_e147_e146_sequence_prefix_comparison(
        _sequence("base", ["a", "b"]), _sequence("candidate", ["a", "x", "c"])
    )
    reverse = e147.build_startup_readiness_e147_e146_sequence_prefix_comparison(
        _sequence("long", ["a", "b", "c"]), _sequence("short", ["a", "b"])
    )
    for record in (divergent, reverse):
        assert record["relation"] == "NOT_PREFIX_EXTENSION"
        assert record["extension_comparison_sha256s"] == []
        assert record["extension_comparison_count"] == 0


def test_e147_propagates_nested_e146_rejection() -> None:
    with pytest.raises(ValueError, match="nested E146 rejected"):
        e147.build_startup_readiness_e147_e146_sequence_prefix_comparison({"reject": True}, _sequence("candidate", ["a", "b"]))


@pytest.mark.parametrize("field,value", [
    ("relation", "IDENTICAL"),
    ("extension_comparison_count", 99),
    ("base_e146_sequence_sha256", "0" * 64),
])
def test_e147_rejects_semantic_forgery(field: str, value: object) -> None:
    record = e147.build_startup_readiness_e147_e146_sequence_prefix_comparison(
        _sequence("base", ["a", "b"]), _sequence("candidate", ["a", "b", "c"])
    )
    record[field] = value
    with pytest.raises(ValueError):
        e147.verify_startup_readiness_e147_e146_sequence_prefix_comparison(record)


def test_e147_rejects_malformed_suffix_boundary_authority_and_digest() -> None:
    original = e147.build_startup_readiness_e147_e146_sequence_prefix_comparison(
        _sequence("base", ["a", "b"]), _sequence("candidate", ["a", "b", "c"])
    )
    mutations = []
    bad_suffix = deepcopy(original); bad_suffix["extension_comparison_sha256s"] = ["not-a-digest"]; mutations.append(bad_suffix)
    no_boundary = deepcopy(original); no_boundary["truth_boundaries"] = []; mutations.append(no_boundary)
    authority = deepcopy(original); authority["authority"]["activation_allowed"] = True; mutations.append(authority)
    digest = deepcopy(original); digest["comparison_sha256"] = "0" * 64; mutations.append(digest)
    for record in mutations:
        with pytest.raises(ValueError):
            e147.verify_startup_readiness_e147_e146_sequence_prefix_comparison(record)
