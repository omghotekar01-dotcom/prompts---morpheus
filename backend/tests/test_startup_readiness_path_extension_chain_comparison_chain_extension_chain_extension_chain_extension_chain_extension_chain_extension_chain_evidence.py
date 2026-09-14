from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest

import app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_evidence as evidence_module
from app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_evidence import (
    build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain,
    verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain,
)


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _contract_hash(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _contract_record(
    *,
    label: str,
    base: str,
    candidate: str,
    relation: str,
    extension_count: int = 0,
) -> dict[str, object]:
    return {
        "comparison_sha256": _contract_hash(f"comparison:{label}"),
        "base_comparison_extension_chain_extension_chain_extension_chain_extension_chain_sha256": _contract_hash(base),
        "candidate_comparison_extension_chain_extension_chain_extension_chain_extension_chain_sha256": _contract_hash(candidate),
        "relation": relation,
        "extension_comparison_count": extension_count,
        "contract_valid": True,
    }


def _readdress_chain(record: dict[str, object]) -> dict[str, object]:
    digest_field = "comparison_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_sha256"
    core = {key: value for key, value in record.items() if key != digest_field}
    return {**core, digest_field: _canonical_sha256(core)}


@pytest.fixture(autouse=True)
def synthetic_nested_verifier(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(record: object) -> dict[str, object]:
        if not isinstance(record, dict) or record.get("contract_valid") is not True:
            raise ValueError("synthetic E137 contract verification failed")
        return deepcopy(record)

    monkeypatch.setattr(
        evidence_module,
        "verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension",
        verify,
    )


@pytest.fixture
def comparison_records() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    first = _contract_record(
        label="strict",
        base="state-a",
        candidate="state-b",
        relation="STRICT_PREFIX_EXTENSION",
        extension_count=2,
    )
    second = _contract_record(
        label="identical",
        base="state-b",
        candidate="state-b",
        relation="IDENTICAL",
    )
    third = _contract_record(
        label="non-prefix",
        base="state-b",
        candidate="state-c",
        relation="NOT_PREFIX_EXTENSION",
    )
    return first, second, third


def test_e137_comparison_chain_replays_deterministically(
    comparison_records: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    first, second, third = comparison_records
    chain = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain(
        [first, second, third]
    )
    replay = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain(
        [first, second, third]
    )

    assert chain == replay
    assert chain["comparison_count"] == 3
    assert chain["comparison_sha256s"] == [first["comparison_sha256"], second["comparison_sha256"], third["comparison_sha256"]]
    assert chain["start_comparison_extension_chain_extension_chain_extension_chain_extension_chain_sha256"] == first[
        "base_comparison_extension_chain_extension_chain_extension_chain_extension_chain_sha256"
    ]
    assert chain["end_comparison_extension_chain_extension_chain_extension_chain_extension_chain_sha256"] == third[
        "candidate_comparison_extension_chain_extension_chain_extension_chain_extension_chain_sha256"
    ]
    assert chain["relation_counts"] == {"IDENTICAL": 1, "STRICT_PREFIX_EXTENSION": 1, "NOT_PREFIX_EXTENSION": 1}
    assert chain["strict_prefix_suffix_comparison_count"] == 2
    assert verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain(
        chain
    ) == chain


def test_e137_comparison_chain_rejects_minimum_duplicate_and_broken_adjacency(
    comparison_records: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    first, second, _ = comparison_records
    with pytest.raises(ValueError, match="at least two comparison records"):
        build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain([first])
    with pytest.raises(ValueError, match="duplicate comparison identities"):
        build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain([first, first])
    with pytest.raises(ValueError, match="broken structural adjacency"):
        build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain([second, first])


def test_e137_comparison_chain_propagates_nested_verifier_failure(
    comparison_records: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    first, second, _ = comparison_records
    invalid = deepcopy(second)
    invalid["contract_valid"] = False
    with pytest.raises(ValueError, match="synthetic E137 contract verification failed"):
        build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain([first, invalid])


def test_e137_comparison_chain_rejects_summary_forgery(
    comparison_records: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    chain = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain(
        list(comparison_records)
    )
    forged = deepcopy(chain)
    forged["relation_counts"]["IDENTICAL"] = 2
    forged["relation_counts"]["NOT_PREFIX_EXTENSION"] = 0
    forged = _readdress_chain(forged)
    with pytest.raises(ValueError, match="relation_counts is inconsistent with embedded comparisons"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain(forged)


def test_e137_comparison_chain_rejects_authority_and_missing_truth_boundaries(
    comparison_records: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    chain = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain(
        list(comparison_records)
    )

    authority = deepcopy(chain)
    authority["authority"]["automatic_control_allowed"] = True
    authority = _readdress_chain(authority)
    with pytest.raises(ValueError, match="cannot carry activation authority"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain(authority)

    missing = deepcopy(chain)
    missing["truth_boundaries"] = []
    missing = _readdress_chain(missing)
    with pytest.raises(ValueError, match="truth boundaries are missing"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain(missing)


def test_e137_comparison_chain_rejects_malformed_identity(
    comparison_records: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    chain = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain(
        list(comparison_records)
    )
    malformed = deepcopy(chain)
    malformed["comparison_sha256s"][0] = "not-a-digest"
    malformed = _readdress_chain(malformed)
    with pytest.raises(ValueError, match="comparison_sha256s is inconsistent with embedded comparisons"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain(malformed)
