from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e151_e150_sequence_prefix_evidence as e151


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _sequence(label: str, ids: list[str]) -> dict[str, object]:
    return {"sequence_sha256": _digest(label), "comparison_sha256s": [_digest(value) for value in ids]}


@pytest.fixture(autouse=True)
def isolate_e150_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E150 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e151, "verify_startup_readiness_e150_e149_comparison_sequence", verify)


def test_e151_replays_deterministically_for_identical_sequences() -> None:
    base = _sequence("s1", ["c1", "c2"])
    first = e151.build_startup_readiness_e151_e150_sequence_prefix_comparison(base, deepcopy(base))
    second = e151.build_startup_readiness_e151_e150_sequence_prefix_comparison(deepcopy(base), deepcopy(base))
    assert first == second
    assert first["relation"] == "IDENTICAL"
    assert first["extension_comparison_sha256s"] == []
    assert first["extension_comparison_count"] == 0
    assert e151.verify_startup_readiness_e151_e150_sequence_prefix_comparison(first) == first


def test_e151_classifies_strict_prefix_and_exposes_exact_suffix() -> None:
    record = e151.build_startup_readiness_e151_e150_sequence_prefix_comparison(
        _sequence("base", ["c1", "c2"]), _sequence("candidate", ["c1", "c2", "c3", "c4"])
    )
    assert record["relation"] == "STRICT_PREFIX_EXTENSION"
    assert record["extension_comparison_sha256s"] == [_digest("c3"), _digest("c4")]
    assert record["extension_comparison_count"] == 2


def test_e151_classifies_divergence_and_reverse_prefix_without_suffix() -> None:
    divergent = e151.build_startup_readiness_e151_e150_sequence_prefix_comparison(
        _sequence("base", ["c1", "c2"]), _sequence("candidate", ["c1", "other", "c3"])
    )
    reverse = e151.build_startup_readiness_e151_e150_sequence_prefix_comparison(
        _sequence("long", ["c1", "c2", "c3"]), _sequence("short", ["c1", "c2"])
    )
    for record in (divergent, reverse):
        assert record["relation"] == "NOT_PREFIX_EXTENSION"
        assert record["extension_comparison_sha256s"] == []
        assert record["extension_comparison_count"] == 0


def test_e151_propagates_nested_e150_rejection() -> None:
    with pytest.raises(ValueError, match="nested E150 rejected"):
        e151.build_startup_readiness_e151_e150_sequence_prefix_comparison(_sequence("base", ["c1", "c2"]), {"reject": True})


@pytest.mark.parametrize("field,value", [
    ("relation", "IDENTICAL"),
    ("extension_comparison_count", 99),
    ("base_e150_sequence_sha256", "0" * 64),
])
def test_e151_rejects_semantic_forgery(field: str, value: object) -> None:
    record = e151.build_startup_readiness_e151_e150_sequence_prefix_comparison(
        _sequence("base", ["c1", "c2"]), _sequence("candidate", ["c1", "c2", "c3"])
    )
    record[field] = value
    with pytest.raises(ValueError):
        e151.verify_startup_readiness_e151_e150_sequence_prefix_comparison(record)


def test_e151_rejects_malformed_identity_suffix_boundary_authority_and_digest() -> None:
    original = e151.build_startup_readiness_e151_e150_sequence_prefix_comparison(
        _sequence("base", ["c1", "c2"]), _sequence("candidate", ["c1", "c2", "c3"])
    )
    malformed = _sequence("candidate", ["c1", "c2", "c3"]); malformed["comparison_sha256s"] = ["bad"]
    with pytest.raises(ValueError, match="exact ordered E149"):
        e151.build_startup_readiness_e151_e150_sequence_prefix_comparison(_sequence("base", ["c1", "c2"]), malformed)
    mutations = []
    bad_suffix = deepcopy(original); bad_suffix["extension_comparison_sha256s"] = ["bad"]; mutations.append(bad_suffix)
    no_boundary = deepcopy(original); no_boundary["truth_boundaries"] = []; mutations.append(no_boundary)
    authority = deepcopy(original); authority["authority"]["activation_allowed"] = True; mutations.append(authority)
    digest = deepcopy(original); digest["comparison_sha256"] = "0" * 64; mutations.append(digest)
    for record in mutations:
        with pytest.raises(ValueError):
            e151.verify_startup_readiness_e151_e150_sequence_prefix_comparison(record)
