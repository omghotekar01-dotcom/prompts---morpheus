from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest

import app.startup_readiness_e140_e139_comparison_sequence_evidence as e140


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _e139_record(label: str, base: str, candidate: str, relation: str, suffix_count: int = 0) -> dict[str, object]:
    return {
        "comparison_sha256": _digest(label),
        "base_comparison_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_sha256": _digest(base),
        "candidate_comparison_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_sha256": _digest(candidate),
        "relation": relation,
        "extension_comparison_count": suffix_count,
    }


def _readdress(record: dict[str, object]) -> dict[str, object]:
    core = {key: value for key, value in record.items() if key != e140.E140_DIGEST_FIELD}
    return {**core, e140.E140_DIGEST_FIELD: _canonical_sha256(core)}


@pytest.fixture
def e139_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    def _verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict):
            raise ValueError("synthetic E139 contract requires a mapping")
        payload = deepcopy(record)
        if payload.get("__reject_nested__") is True:
            raise ValueError("synthetic nested E139 verification failure")
        required = [
            "comparison_sha256",
            "base_comparison_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_sha256",
            "candidate_comparison_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_sha256",
        ]
        if not all(isinstance(payload.get(field), str) and len(payload[field]) == 64 for field in required):
            raise ValueError("synthetic E139 contract contains malformed identities")
        if payload.get("relation") not in ("IDENTICAL", "STRICT_PREFIX_EXTENSION", "NOT_PREFIX_EXTENSION"):
            raise ValueError("synthetic E139 contract contains unsupported relation")
        if not isinstance(payload.get("extension_comparison_count"), int) or payload["extension_comparison_count"] < 0:
            raise ValueError("synthetic E139 contract contains malformed suffix count")
        return payload

    monkeypatch.setattr(
        e140,
        "verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension",
        _verify,
    )


def _records() -> list[dict[str, object]]:
    return [
        _e139_record("r1", "a", "b", "STRICT_PREFIX_EXTENSION", 2),
        _e139_record("r2", "b", "c", "IDENTICAL", 0),
        _e139_record("r3", "c", "d", "NOT_PREFIX_EXTENSION", 0),
    ]


def test_e140_sequence_replays_deterministically_and_summarizes(e139_contract: None) -> None:
    records = _records()
    first = e140.build_startup_readiness_e140_e139_comparison_sequence(records)
    second = e140.build_startup_readiness_e140_e139_comparison_sequence(records)
    assert first == second
    assert first["comparison_count"] == 3
    assert first["comparison_sha256s"] == [record["comparison_sha256"] for record in records]
    assert first["relation_counts"] == {
        "IDENTICAL": 1,
        "STRICT_PREFIX_EXTENSION": 1,
        "NOT_PREFIX_EXTENSION": 1,
    }
    assert first["strict_prefix_suffix_comparison_count"] == 2
    assert first["start_e138_chain_sha256"] == records[0]["base_comparison_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_sha256"]
    assert first["end_e138_chain_sha256"] == records[-1]["candidate_comparison_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_sha256"]
    assert e140.verify_startup_readiness_e140_e139_comparison_sequence(first) == first


def test_e140_sequence_rejects_minimum_duplicates_and_broken_adjacency(e139_contract: None) -> None:
    records = _records()
    with pytest.raises(ValueError, match="at least two"):
        e140.build_startup_readiness_e140_e139_comparison_sequence(records[:1])

    duplicate = [records[0], deepcopy(records[0])]
    with pytest.raises(ValueError, match="duplicate"):
        e140.build_startup_readiness_e140_e139_comparison_sequence(duplicate)

    broken = deepcopy(records)
    broken[1]["base_comparison_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_sha256"] = _digest("other")
    with pytest.raises(ValueError, match="broken structural adjacency"):
        e140.build_startup_readiness_e140_e139_comparison_sequence(broken)


def test_e140_sequence_propagates_nested_rejection_and_rejects_summary_forgery(e139_contract: None) -> None:
    record = e140.build_startup_readiness_e140_e139_comparison_sequence(_records())

    nested = deepcopy(record)
    nested["comparisons"][1]["__reject_nested__"] = True
    nested = _readdress(nested)
    with pytest.raises(ValueError, match="synthetic nested E139 verification failure"):
        e140.verify_startup_readiness_e140_e139_comparison_sequence(nested)

    forged = deepcopy(record)
    forged["relation_counts"]["IDENTICAL"] = 2
    forged = _readdress(forged)
    with pytest.raises(ValueError, match="relation_counts is inconsistent"):
        e140.verify_startup_readiness_e140_e139_comparison_sequence(forged)


def test_e140_sequence_rejects_malformed_identity_truth_boundary_and_authority(e139_contract: None) -> None:
    record = e140.build_startup_readiness_e140_e139_comparison_sequence(_records())

    malformed = deepcopy(record)
    malformed["comparison_sha256s"][0] = "not-a-digest"
    malformed = _readdress(malformed)
    with pytest.raises(ValueError, match="comparison_sha256s is inconsistent"):
        e140.verify_startup_readiness_e140_e139_comparison_sequence(malformed)

    missing = deepcopy(record)
    missing["truth_boundaries"] = []
    missing = _readdress(missing)
    with pytest.raises(ValueError, match="truth boundaries are missing"):
        e140.verify_startup_readiness_e140_e139_comparison_sequence(missing)

    authority = deepcopy(record)
    authority["authority"]["production_deployment_authorized"] = True
    authority = _readdress(authority)
    with pytest.raises(ValueError, match="cannot carry activation authority"):
        e140.verify_startup_readiness_e140_e139_comparison_sequence(authority)
