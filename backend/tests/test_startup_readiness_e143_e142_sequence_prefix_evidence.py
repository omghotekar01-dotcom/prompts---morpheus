from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

import app.startup_readiness_e143_e142_sequence_prefix_evidence as e143


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _sequence(label: str, comparisons: list[str]) -> dict[str, object]:
    return {
        "sequence_sha256": _digest(label),
        "comparison_sha256s": [_digest(item) for item in comparisons],
    }


@pytest.fixture(autouse=True)
def isolate_e142_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("reject"):
            raise ValueError("nested E142 rejected")
        return deepcopy(record)
    monkeypatch.setattr(e143, "verify_startup_readiness_e142_e141_comparison_sequence", verify)


def test_e143_identical_replays_deterministically() -> None:
    base = _sequence("s1", ["a", "b"])
    candidate = deepcopy(base)
    first = e143.build_startup_readiness_e143_e142_sequence_prefix_comparison(base, candidate)
    second = e143.build_startup_readiness_e143_e142_sequence_prefix_comparison(base, candidate)
    assert first == second
    assert first["relation"] == "IDENTICAL"
    assert first["extension_comparison_sha256s"] == []
    assert first["extension_comparison_count"] == 0
    assert e143.verify_startup_readiness_e143_e142_sequence_prefix_comparison(first) == first


def test_e143_classifies_strict_prefix_and_exposes_exact_suffix() -> None:
    base = _sequence("base", ["a", "b"])
    candidate = _sequence("candidate", ["a", "b", "c", "d"])
    record = e143.build_startup_readiness_e143_e142_sequence_prefix_comparison(base, candidate)
    assert record["relation"] == "STRICT_PREFIX_EXTENSION"
    assert record["extension_comparison_sha256s"] == [_digest("c"), _digest("d")]
    assert record["extension_comparison_count"] == 2


def test_e143_rejects_divergent_and_reverse_prefix_as_extensions() -> None:
    base = _sequence("base", ["a", "b"])
    divergent = _sequence("divergent", ["a", "x", "c"])
    reverse = _sequence("reverse", ["a"])
    assert e143.build_startup_readiness_e143_e142_sequence_prefix_comparison(base, divergent)["relation"] == "NOT_PREFIX_EXTENSION"
    assert e143.build_startup_readiness_e143_e142_sequence_prefix_comparison(base, reverse)["relation"] == "NOT_PREFIX_EXTENSION"


def test_e143_propagates_nested_rejection() -> None:
    base = _sequence("base", ["a", "b"])
    candidate = _sequence("candidate", ["a", "b", "c"])
    candidate["reject"] = True
    with pytest.raises(ValueError, match="nested E142 rejected"):
        e143.build_startup_readiness_e143_e142_sequence_prefix_comparison(base, candidate)


def test_e143_rejects_semantic_forgery_and_malformed_suffix() -> None:
    record = e143.build_startup_readiness_e143_e142_sequence_prefix_comparison(
        _sequence("base", ["a", "b"]), _sequence("candidate", ["a", "b", "c"])
    )
    forged = deepcopy(record)
    forged["relation"] = "IDENTICAL"
    with pytest.raises(ValueError, match="relation"):
        e143.verify_startup_readiness_e143_e142_sequence_prefix_comparison(forged)
    malformed = deepcopy(record)
    malformed["extension_comparison_sha256s"] = ["bad"]
    with pytest.raises(ValueError):
        e143.verify_startup_readiness_e143_e142_sequence_prefix_comparison(malformed)


def test_e143_rejects_missing_boundaries_authority_escalation_and_digest_tampering() -> None:
    record = e143.build_startup_readiness_e143_e142_sequence_prefix_comparison(
        _sequence("base", ["a", "b"]), _sequence("candidate", ["a", "b", "c"])
    )
    missing = deepcopy(record)
    missing["truth_boundaries"] = []
    with pytest.raises(ValueError, match="truth boundaries"):
        e143.verify_startup_readiness_e143_e142_sequence_prefix_comparison(missing)
    escalated = deepcopy(record)
    escalated["authority"]["production_deployment_authorized"] = True
    with pytest.raises(ValueError, match="authority"):
        e143.verify_startup_readiness_e143_e142_sequence_prefix_comparison(escalated)
    tampered = deepcopy(record)
    tampered[e143.E143_DIGEST_FIELD] = _digest("forged")
    with pytest.raises(ValueError, match="digest"):
        e143.verify_startup_readiness_e143_e142_sequence_prefix_comparison(tampered)
