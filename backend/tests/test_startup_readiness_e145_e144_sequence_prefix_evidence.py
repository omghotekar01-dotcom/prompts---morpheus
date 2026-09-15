from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e145_e144_sequence_prefix_evidence as e145


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _sequence(label: str, comparisons: list[str]) -> dict[str, object]:
    return {"sequence_sha256": _digest(label), "comparison_sha256s": [_digest(item) for item in comparisons]}


@pytest.fixture(autouse=True)
def isolate_e144_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E144 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e145, "verify_startup_readiness_e144_e143_comparison_sequence", verify)


def test_e145_identical_replays_deterministically() -> None:
    base = _sequence("s1", ["a", "b"])
    candidate = deepcopy(base)
    first = e145.build_startup_readiness_e145_e144_sequence_prefix_comparison(base, candidate)
    second = e145.build_startup_readiness_e145_e144_sequence_prefix_comparison(base, candidate)
    assert first == second
    assert first["relation"] == "IDENTICAL"
    assert first["extension_comparison_sha256s"] == []
    assert first["extension_comparison_count"] == 0
    assert e145.verify_startup_readiness_e145_e144_sequence_prefix_comparison(first) == first


def test_e145_classifies_strict_prefix_and_exposes_exact_suffix() -> None:
    record = e145.build_startup_readiness_e145_e144_sequence_prefix_comparison(
        _sequence("base", ["a", "b"]), _sequence("candidate", ["a", "b", "c", "d"])
    )
    assert record["relation"] == "STRICT_PREFIX_EXTENSION"
    assert record["extension_comparison_sha256s"] == [_digest("c"), _digest("d")]
    assert record["extension_comparison_count"] == 2


def test_e145_classifies_divergent_and_reverse_prefix_as_not_extensions() -> None:
    base = _sequence("base", ["a", "b"])
    divergent = _sequence("divergent", ["a", "x", "c"])
    reverse = _sequence("reverse", ["a"])
    assert e145.build_startup_readiness_e145_e144_sequence_prefix_comparison(base, divergent)["relation"] == "NOT_PREFIX_EXTENSION"
    assert e145.build_startup_readiness_e145_e144_sequence_prefix_comparison(base, reverse)["relation"] == "NOT_PREFIX_EXTENSION"


def test_e145_propagates_nested_rejection() -> None:
    candidate = _sequence("candidate", ["a", "b", "c"])
    candidate["reject"] = True
    with pytest.raises(ValueError, match="nested E144 rejected"):
        e145.build_startup_readiness_e145_e144_sequence_prefix_comparison(_sequence("base", ["a", "b"]), candidate)


def test_e145_rejects_semantic_forgery_and_malformed_suffix() -> None:
    record = e145.build_startup_readiness_e145_e144_sequence_prefix_comparison(
        _sequence("base", ["a", "b"]), _sequence("candidate", ["a", "b", "c"])
    )
    forged = deepcopy(record)
    forged["relation"] = "IDENTICAL"
    with pytest.raises(ValueError, match="relation"):
        e145.verify_startup_readiness_e145_e144_sequence_prefix_comparison(forged)
    malformed = deepcopy(record)
    malformed["extension_comparison_sha256s"] = ["bad"]
    with pytest.raises(ValueError):
        e145.verify_startup_readiness_e145_e144_sequence_prefix_comparison(malformed)


def test_e145_rejects_missing_boundaries_authority_escalation_and_digest_tampering() -> None:
    record = e145.build_startup_readiness_e145_e144_sequence_prefix_comparison(
        _sequence("base", ["a", "b"]), _sequence("candidate", ["a", "b", "c"])
    )
    missing = deepcopy(record)
    missing["truth_boundaries"] = []
    with pytest.raises(ValueError, match="truth boundaries"):
        e145.verify_startup_readiness_e145_e144_sequence_prefix_comparison(missing)
    escalated = deepcopy(record)
    escalated["authority"]["automatic_control_allowed"] = True
    with pytest.raises(ValueError, match="authority"):
        e145.verify_startup_readiness_e145_e144_sequence_prefix_comparison(escalated)
    tampered = deepcopy(record)
    tampered[e145.E145_DIGEST_FIELD] = _digest("forged")
    with pytest.raises(ValueError, match="digest"):
        e145.verify_startup_readiness_e145_e144_sequence_prefix_comparison(tampered)
