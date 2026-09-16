from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e153_e152_sequence_prefix_evidence as e153


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _sequence(label: str, ids: list[str]) -> dict[str, object]:
    return {"sequence_sha256": _digest(label), "comparison_sha256s": [_digest(value) for value in ids]}


@pytest.fixture(autouse=True)
def isolate_e152_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E152 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e153, "verify_startup_readiness_e152_e151_comparison_sequence", verify)


def test_e153_replays_deterministically_for_identical_sequences() -> None:
    base = _sequence("s1", ["c1", "c2"])
    first = e153.build_startup_readiness_e153_e152_sequence_prefix_comparison(base, deepcopy(base))
    second = e153.build_startup_readiness_e153_e152_sequence_prefix_comparison(deepcopy(base), deepcopy(base))
    assert first == second
    assert first["relation"] == "IDENTICAL"
    assert first["extension_comparison_sha256s"] == []
    assert first["extension_comparison_count"] == 0
    assert e153.verify_startup_readiness_e153_e152_sequence_prefix_comparison(first) == first


def test_e153_classifies_strict_prefix_and_exposes_exact_suffix() -> None:
    record = e153.build_startup_readiness_e153_e152_sequence_prefix_comparison(
        _sequence("base", ["c1", "c2"]), _sequence("candidate", ["c1", "c2", "c3", "c4"])
    )
    assert record["relation"] == "STRICT_PREFIX_EXTENSION"
    assert record["extension_comparison_sha256s"] == [_digest("c3"), _digest("c4")]
    assert record["extension_comparison_count"] == 2


def test_e153_classifies_divergence_and_reverse_prefix_without_suffix() -> None:
    divergent = e153.build_startup_readiness_e153_e152_sequence_prefix_comparison(
        _sequence("base", ["c1", "c2"]), _sequence("candidate", ["c1", "other", "c3"])
    )
    reverse = e153.build_startup_readiness_e153_e152_sequence_prefix_comparison(
        _sequence("long", ["c1", "c2", "c3"]), _sequence("short", ["c1", "c2"])
    )
    for record in (divergent, reverse):
        assert record["relation"] == "NOT_PREFIX_EXTENSION"
        assert record["extension_comparison_sha256s"] == []
        assert record["extension_comparison_count"] == 0


def test_e153_propagates_nested_e152_rejection() -> None:
    with pytest.raises(ValueError, match="nested E152 rejected"):
        e153.build_startup_readiness_e153_e152_sequence_prefix_comparison(_sequence("base", ["c1", "c2"]), {"reject": True})


@pytest.mark.parametrize("field,value", [
    ("relation", "IDENTICAL"),
    ("extension_comparison_count", 99),
    ("base_e152_sequence_sha256", "0" * 64),
])
def test_e153_rejects_semantic_forgery(field: str, value: object) -> None:
    record = e153.build_startup_readiness_e153_e152_sequence_prefix_comparison(
        _sequence("base", ["c1", "c2"]), _sequence("candidate", ["c1", "c2", "c3"])
    )
    record[field] = value
    with pytest.raises(ValueError):
        e153.verify_startup_readiness_e153_e152_sequence_prefix_comparison(record)


def test_e153_rejects_malformed_identity_suffix_boundary_authority_and_digest() -> None:
    original = e153.build_startup_readiness_e153_e152_sequence_prefix_comparison(
        _sequence("base", ["c1", "c2"]), _sequence("candidate", ["c1", "c2", "c3"])
    )
    malformed = _sequence("candidate", ["c1", "c2", "c3"]); malformed["comparison_sha256s"] = ["bad"]
    with pytest.raises(ValueError, match="exact ordered E151"):
        e153.build_startup_readiness_e153_e152_sequence_prefix_comparison(_sequence("base", ["c1", "c2"]), malformed)
    mutations = []
    bad_suffix = deepcopy(original); bad_suffix["extension_comparison_sha256s"] = ["bad"]; mutations.append(bad_suffix)
    no_boundary = deepcopy(original); no_boundary["truth_boundaries"] = []; mutations.append(no_boundary)
    authority = deepcopy(original); authority["authority"]["activation_allowed"] = True; mutations.append(authority)
    digest = deepcopy(original); digest["comparison_sha256"] = "0" * 64; mutations.append(digest)
    for record in mutations:
        with pytest.raises(ValueError):
            e153.verify_startup_readiness_e153_e152_sequence_prefix_comparison(record)
