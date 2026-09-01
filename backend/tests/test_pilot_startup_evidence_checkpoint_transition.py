from __future__ import annotations

import pytest

from app.pilot_startup_evidence_checkpoint_chain import (
    build_pilot_startup_evidence_checkpoint_chain,
)
from app.pilot_startup_evidence_checkpoint_transition import (
    build_pilot_startup_evidence_checkpoint_transition,
    verify_pilot_startup_evidence_checkpoint_transition,
)


def _chain(*digests: str) -> dict:
    return build_pilot_startup_evidence_checkpoint_chain(digests)


def test_transition_binds_exact_one_checkpoint_extension() -> None:
    previous = _chain("a" * 64)
    next_chain = _chain("a" * 64, "b" * 64)

    transition = build_pilot_startup_evidence_checkpoint_transition(previous, next_chain)

    assert transition["previous_chain_sha256"] == previous["chain_sha256"]
    assert transition["next_chain_sha256"] == next_chain["chain_sha256"]
    assert transition["appended_catalog_sha256"] == "b" * 64
    assert transition["previous_checkpoint_count"] == 1
    assert transition["next_checkpoint_count"] == 2
    assert transition["production_deployment_authorized"] is False
    assert verify_pilot_startup_evidence_checkpoint_transition(transition, previous, next_chain)


def test_transition_is_deterministic() -> None:
    previous = _chain("a" * 64, "b" * 64)
    next_chain = _chain("a" * 64, "b" * 64, "c" * 64)

    first = build_pilot_startup_evidence_checkpoint_transition(previous, next_chain)
    second = build_pilot_startup_evidence_checkpoint_transition(previous, next_chain)

    assert first == second


@pytest.mark.parametrize(
    "next_chain",
    [
        _chain("b" * 64, "a" * 64),
        _chain("a" * 64, "b" * 64, "c" * 64),
        _chain("b" * 64, "c" * 64),
    ],
)
def test_transition_builder_rejects_non_extensions(next_chain: dict) -> None:
    previous = _chain("a" * 64)

    with pytest.raises(ValueError, match="exact one-catalog extension"):
        build_pilot_startup_evidence_checkpoint_transition(previous, next_chain)


def test_transition_verifier_rejects_tampering_and_wrong_chains() -> None:
    previous = _chain("a" * 64)
    next_chain = _chain("a" * 64, "b" * 64)
    transition = build_pilot_startup_evidence_checkpoint_transition(previous, next_chain)

    for key, value in (
        ("previous_chain_sha256", "f" * 64),
        ("next_chain_sha256", "e" * 64),
        ("appended_catalog_sha256", "d" * 64),
        ("transition_sha256", "c" * 64),
    ):
        tampered = dict(transition)
        tampered[key] = value
        assert not verify_pilot_startup_evidence_checkpoint_transition(tampered, previous, next_chain)

    wrong_previous = _chain("f" * 64)
    wrong_next = _chain("f" * 64, "b" * 64)
    assert not verify_pilot_startup_evidence_checkpoint_transition(
        transition, wrong_previous, next_chain
    )
    assert not verify_pilot_startup_evidence_checkpoint_transition(
        transition, previous, wrong_next
    )


def test_transition_verifier_rejects_authority_widening_boolean_alias_and_extra_fields() -> None:
    previous = _chain("a" * 64)
    next_chain = _chain("a" * 64, "b" * 64)
    transition = build_pilot_startup_evidence_checkpoint_transition(previous, next_chain)

    tampered = dict(transition)
    tampered["production_deployment_authorized"] = True
    assert not verify_pilot_startup_evidence_checkpoint_transition(tampered, previous, next_chain)

    tampered = dict(transition)
    tampered["previous_checkpoint_count"] = True
    assert not verify_pilot_startup_evidence_checkpoint_transition(tampered, previous, next_chain)

    tampered = dict(transition)
    tampered["next_checkpoint_count"] = True
    assert not verify_pilot_startup_evidence_checkpoint_transition(tampered, previous, next_chain)

    tampered = dict(transition)
    tampered["unexpected"] = "field"
    assert not verify_pilot_startup_evidence_checkpoint_transition(tampered, previous, next_chain)
