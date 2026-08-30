from dataclasses import replace

import pytest

from reproduction_attestation import build_reproduction_attestation, verify_reproduction_attestation


def _h(ch: str) -> str:
    return ch * 64


def test_attestation_is_deterministic_and_verifiable():
    kwargs = dict(
        source_revision="a" * 40,
        reproduction_pack_sha256=_h("1"),
        environment_sha256=_h("2"),
        workload_sha256=_h("3"),
        results_sha256=_h("4"),
        commands_sha256=_h("5"),
        verifier_ids=["lab-b", "lab-a", "lab-a"],
        verified_at="2026-08-31T04:30:00+05:30",
    )
    first = build_reproduction_attestation(**kwargs)
    second = build_reproduction_attestation(**kwargs)
    assert first == second
    assert first.verifier_ids == ("lab-a", "lab-b")
    assert first.verified_at == "2026-08-30T23:00:00Z"
    assert verify_reproduction_attestation(first)


def test_tampering_breaks_verification():
    attestation = build_reproduction_attestation(
        source_revision="b" * 40,
        reproduction_pack_sha256=_h("1"),
        environment_sha256=_h("2"),
        workload_sha256=_h("3"),
        results_sha256=_h("4"),
        commands_sha256=_h("5"),
        verifier_ids=["lab-a"],
        verified_at="2026-08-31T00:00:00Z",
    )
    assert not verify_reproduction_attestation(replace(attestation, results_sha256=_h("6")))


def test_evidence_aliasing_and_naive_time_fail_closed():
    with pytest.raises(ValueError, match="distinct"):
        build_reproduction_attestation(
            source_revision="c" * 40,
            reproduction_pack_sha256=_h("1"),
            environment_sha256=_h("1"),
            workload_sha256=_h("3"),
            results_sha256=_h("4"),
            commands_sha256=_h("5"),
            verifier_ids=["lab-a"],
            verified_at="2026-08-31T00:00:00Z",
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        build_reproduction_attestation(
            source_revision="c" * 40,
            reproduction_pack_sha256=_h("1"),
            environment_sha256=_h("2"),
            workload_sha256=_h("3"),
            results_sha256=_h("4"),
            commands_sha256=_h("5"),
            verifier_ids=["lab-a"],
            verified_at="2026-08-31T00:00:00",
        )
