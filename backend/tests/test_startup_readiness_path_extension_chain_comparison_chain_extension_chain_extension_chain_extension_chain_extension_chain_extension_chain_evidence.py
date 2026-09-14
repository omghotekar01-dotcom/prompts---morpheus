from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.server import app
from app.startup_readiness_evidence import build_startup_readiness_coherence_transition, build_startup_readiness_evidence, compare_startup_readiness_evidence_to_current
from app.startup_readiness_path_evidence import build_startup_readiness_coherence_path
from app.startup_readiness_path_extension_evidence import build_startup_readiness_coherence_path_extension
from app.startup_readiness_path_extension_chain_evidence import build_startup_readiness_coherence_path_extension_chain
from app.startup_readiness_path_extension_chain_extension_evidence import build_startup_readiness_coherence_path_extension_chain_extension
from app.startup_readiness_path_extension_chain_comparison_chain_evidence import build_startup_readiness_coherence_path_extension_chain_comparison_chain
from app.startup_readiness_path_extension_chain_comparison_chain_extension_evidence import build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension
from app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_evidence import build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain
from app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_evidence import build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension
from app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_chain_evidence import build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain
from app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_evidence import build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension
from app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_evidence import build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain
from app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_evidence import build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension
from app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_evidence import build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain
from app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_evidence import build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension
from app.startup_readiness_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_evidence import (
    build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain,
    verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain,
)


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _readdress_readiness(readiness: dict[str, object]) -> dict[str, object]:
    core = {key: value for key, value in readiness.items() if key != "readiness_sha256"}
    return {**core, "readiness_sha256": _canonical_sha256(core)}


def _readdress_chain(record: dict[str, object]) -> dict[str, object]:
    core = {
        key: value
        for key, value in record.items()
        if key != "comparison_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_sha256"
    }
    return {**core, "comparison_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain_sha256": _canonical_sha256(core)}


def _report(current: dict[str, object], system: str | None = None) -> dict[str, object]:
    historical = deepcopy(current)
    if system is not None:
        historical["environment"]["system"] = system
        historical = _readdress_readiness(historical)
    return compare_startup_readiness_evidence_to_current(build_startup_readiness_evidence(historical), current)


def _e136_chains() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    current = TestClient(app).get("/api/v2/system/startup-mvp-readiness").json()
    reports = [_report(current), _report(current, "hist-a"), _report(current, "hist-b"), _report(current, "hist-c")]
    transitions = [build_startup_readiness_coherence_transition(reports[i], reports[i + 1]) for i in range(3)]
    path2 = build_startup_readiness_coherence_path(transitions[:2])
    path3 = build_startup_readiness_coherence_path(transitions[:3])
    ext22 = build_startup_readiness_coherence_path_extension(path2, path2)
    ext23 = build_startup_readiness_coherence_path_extension(path2, path3)
    ext33 = build_startup_readiness_coherence_path_extension(path3, path3)
    echain2 = build_startup_readiness_coherence_path_extension_chain([ext22, ext23])
    echain3 = build_startup_readiness_coherence_path_extension_chain([ext22, ext23, ext33])
    p22 = build_startup_readiness_coherence_path_extension_chain_extension(echain2, echain2)
    p23 = build_startup_readiness_coherence_path_extension_chain_extension(echain2, echain3)
    p33 = build_startup_readiness_coherence_path_extension_chain_extension(echain3, echain3)
    cchain2 = build_startup_readiness_coherence_path_extension_chain_comparison_chain([p22, p23])
    cchain3 = build_startup_readiness_coherence_path_extension_chain_comparison_chain([p22, p23, p33])
    strict = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension(cchain2, cchain3)
    identical = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension(cchain3, cchain3)
    reverse = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension(cchain3, cchain2)
    base = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain([strict, identical])
    extended = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain([strict, identical, reverse])
    first = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension(base, extended)
    second = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension(extended, extended)
    third = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension(extended, base)
    chain2 = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain([first, second])
    chain3 = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain([first, second, third])
    r1 = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension(chain2, chain3)
    r2 = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension(chain3, chain3)
    r3 = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension(chain3, chain2)
    base_chain = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain([r1, r2])
    extended_chain = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain([r1, r2, r3])
    first_e135 = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension(
        base_chain, extended_chain
    )
    second_e135 = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension(
        extended_chain, extended_chain
    )
    third_e135 = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension(
        extended_chain, base_chain
    )
    base_e136 = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain(
        [first_e135, second_e135]
    )
    extended_e136 = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain(
        [first_e135, second_e135, third_e135]
    )
    divergent_e136 = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain(
        [second_e135, third_e135]
    )
    return base_e136, extended_e136, divergent_e136


def _e137_records() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    base, extended, _ = _e136_chains()
    strict = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
        base, extended
    )
    identical = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
        extended, extended
    )
    reverse = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension(
        extended, base
    )
    return strict, identical, reverse


def test_e137_comparison_chain_replays_deterministically() -> None:
    first, second, third = _e137_records()
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
    assert chain["strict_prefix_suffix_comparison_count"] == first["extension_comparison_count"]
    assert verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain(
        chain
    ) == chain


def test_e137_comparison_chain_rejects_minimum_duplicate_and_broken_adjacency() -> None:
    first, second, _ = _e137_records()
    with pytest.raises(ValueError, match="at least two comparison records"):
        build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain(
            [first]
        )
    with pytest.raises(ValueError, match="duplicate comparison identities"):
        build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain(
            [first, first]
        )
    with pytest.raises(ValueError, match="broken structural adjacency"):
        build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain(
            [second, first]
        )


def test_e137_comparison_chain_rejects_nested_tampering_and_summary_forgery() -> None:
    first, second, third = _e137_records()
    chain = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain(
        [first, second, third]
    )

    tampered = deepcopy(chain)
    tampered["comparisons"][1]["comparison_sha256"] = "0" * 64
    tampered = _readdress_chain(tampered)
    with pytest.raises(ValueError, match="comparison digest does not match canonical record"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain(
            tampered
        )

    forged = deepcopy(chain)
    forged["relation_counts"]["IDENTICAL"] = 2
    forged["relation_counts"]["NOT_PREFIX_EXTENSION"] = 0
    forged = _readdress_chain(forged)
    with pytest.raises(ValueError, match="relation_counts is inconsistent with embedded comparisons"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain(
            forged
        )


def test_e137_comparison_chain_rejects_authority_boundaries_and_malformed_identity() -> None:
    first, second, third = _e137_records()
    chain = build_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain(
        [first, second, third]
    )

    authority = deepcopy(chain)
    authority["authority"]["automatic_control_allowed"] = True
    authority = _readdress_chain(authority)
    with pytest.raises(ValueError, match="cannot carry activation authority"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain(
            authority
        )

    missing = deepcopy(chain)
    missing["truth_boundaries"] = []
    missing = _readdress_chain(missing)
    with pytest.raises(ValueError, match="truth boundaries are missing"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain(
            missing
        )

    malformed = deepcopy(chain)
    malformed["comparison_sha256s"][0] = "not-a-digest"
    malformed = _readdress_chain(malformed)
    with pytest.raises(ValueError, match="comparison_sha256s is inconsistent with embedded comparisons"):
        verify_startup_readiness_coherence_path_extension_chain_comparison_chain_extension_chain_extension_chain_extension_chain_extension_chain_extension_chain(
            malformed
        )
