from dataclasses import replace

import pytest

from reproduction_attestation import build_reproduction_attestation
from reproduction_consensus import build_reproduction_consensus, verify_reproduction_consensus


def _h(ch: str) -> str:
    return ch * 64


def _attestation(verifier: str, env: str, commands: str, when: str):
    return build_reproduction_attestation(
        source_revision="a" * 40,
        reproduction_pack_sha256=_h("1"),
        environment_sha256=_h(env),
        workload_sha256=_h("3"),
        results_sha256=_h("4"),
        commands_sha256=_h(commands),
        verifier_ids=[verifier],
        verified_at=when,
    )


def test_two_independent_labs_form_deterministic_consensus():
    a = _attestation("lab-a", "2", "5", "2026-08-31T00:00:00Z")
    b = _attestation("lab-b", "6", "7", "2026-08-31T00:05:00Z")
    first = build_reproduction_consensus([a, b])
    second = build_reproduction_consensus([b, a])
    assert first == second
    assert first.independent_lab_count == 2
    assert first.verifier_ids == ("lab-a", "lab-b")
    assert verify_reproduction_consensus(first)


def test_shared_verifier_is_not_independent():
    a = _attestation("lab-a", "2", "5", "2026-08-31T00:00:00Z")
    b = _attestation("lab-a", "6", "7", "2026-08-31T00:05:00Z")
    with pytest.raises(ValueError, match="share verifier"):
        build_reproduction_consensus([a, b])


def test_disagreeing_result_lineage_fails_closed():
    a = _attestation("lab-a", "2", "5", "2026-08-31T00:00:00Z")
    b = replace(_attestation("lab-b", "6", "7", "2026-08-31T00:05:00Z"), results_sha256=_h("8"))
    with pytest.raises(ValueError):
        build_reproduction_consensus([a, b])


def test_consensus_digest_detects_tampering():
    a = _attestation("lab-a", "2", "5", "2026-08-31T00:00:00Z")
    b = _attestation("lab-b", "6", "7", "2026-08-31T00:05:00Z")
    consensus = build_reproduction_consensus([a, b])
    assert not verify_reproduction_consensus(replace(consensus, results_sha256=_h("8")))


def test_required_lab_count_must_be_real_integer_and_satisfied():
    a = _attestation("lab-a", "2", "5", "2026-08-31T00:00:00Z")
    b = _attestation("lab-b", "6", "7", "2026-08-31T00:05:00Z")
    with pytest.raises(ValueError):
        build_reproduction_consensus([a, b], required_lab_count=True)
    with pytest.raises(ValueError, match="not enough"):
        build_reproduction_consensus([a, b], required_lab_count=3)
