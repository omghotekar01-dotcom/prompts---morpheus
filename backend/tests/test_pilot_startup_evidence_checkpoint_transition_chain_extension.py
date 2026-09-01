from __future__ import annotations

import pytest

from app.pilot_startup_evidence_checkpoint_chain import (
    build_pilot_startup_evidence_checkpoint_chain,
)
from app.pilot_startup_evidence_checkpoint_transition import (
    build_pilot_startup_evidence_checkpoint_transition,
)
from app.pilot_startup_evidence_checkpoint_transition_chain import (
    build_pilot_startup_evidence_checkpoint_transition_chain,
)
from app.pilot_startup_evidence_checkpoint_transition_chain_extension import (
    build_pilot_startup_evidence_checkpoint_transition_chain_extension,
    verify_pilot_startup_evidence_checkpoint_transition_chain_extension,
)


def _path():
    c1 = build_pilot_startup_evidence_checkpoint_chain(["a" * 64])
    c2 = build_pilot_startup_evidence_checkpoint_chain(["a" * 64, "b" * 64])
    c3 = build_pilot_startup_evidence_checkpoint_chain(["a" * 64, "b" * 64, "c" * 64])
    c4 = build_pilot_startup_evidence_checkpoint_chain(
        ["a" * 64, "b" * 64, "c" * 64, "d" * 64]
    )
    t1 = build_pilot_startup_evidence_checkpoint_transition(c1, c2)
    t2 = build_pilot_startup_evidence_checkpoint_transition(c2, c3)
    t3 = build_pilot_startup_evidence_checkpoint_transition(c3, c4)
    e1 = (t1, c1, c2)
    e2 = (t2, c2, c3)
    e3 = (t3, c3, c4)
    return (c1, c2, c3, c4), (e1, e2, e3)


def _valid_extension():
    _chains, evidence = _path()
    previous_evidence = [evidence[0]]
    next_evidence = [evidence[0], evidence[1]]
    previous = build_pilot_startup_evidence_checkpoint_transition_chain(previous_evidence)
    next_chain = build_pilot_startup_evidence_checkpoint_transition_chain(next_evidence)
    artifact = build_pilot_startup_evidence_checkpoint_transition_chain_extension(
        previous,
        previous_evidence,
        next_chain,
        next_evidence,
    )
    return artifact, previous, previous_evidence, next_chain, next_evidence


def test_transition_chain_extension_is_deterministic_and_independently_verifiable() -> None:
    artifact, previous, previous_evidence, next_chain, next_evidence = _valid_extension()
    rebuilt = build_pilot_startup_evidence_checkpoint_transition_chain_extension(
        previous,
        previous_evidence,
        next_chain,
        next_evidence,
    )

    assert rebuilt == artifact
    assert artifact["previous_transition_count"] == 1
    assert artifact["next_transition_count"] == 2
    assert artifact["appended_transition_sha256"] == next_chain["transition_sha256_chain"][-1]
    assert artifact["production_deployment_authorized"] is False
    assert verify_pilot_startup_evidence_checkpoint_transition_chain_extension(
        artifact,
        previous,
        previous_evidence,
        next_chain,
        next_evidence,
    )


def test_transition_chain_extension_rejects_multi_transition_jump() -> None:
    _chains, evidence = _path()
    previous_evidence = [evidence[0]]
    next_evidence = list(evidence)
    previous = build_pilot_startup_evidence_checkpoint_transition_chain(previous_evidence)
    next_chain = build_pilot_startup_evidence_checkpoint_transition_chain(next_evidence)

    with pytest.raises(ValueError, match="append exactly one"):
        build_pilot_startup_evidence_checkpoint_transition_chain_extension(
            previous, previous_evidence, next_chain, next_evidence
        )


def test_transition_chain_extension_rejects_forked_or_reordered_prefix() -> None:
    chains, evidence = _path()
    c1, _c2, c3, c4 = chains
    previous_evidence = [evidence[0]]
    previous = build_pilot_startup_evidence_checkpoint_transition_chain(previous_evidence)
    fork_transition = build_pilot_startup_evidence_checkpoint_transition(c1, c3)
    assert fork_transition["next_checkpoint_count"] == 3

    with pytest.raises(ValueError, match="append exactly one"):
        build_pilot_startup_evidence_checkpoint_transition_chain_extension(
            previous,
            previous_evidence,
            build_pilot_startup_evidence_checkpoint_transition_chain([evidence[1], evidence[2]]),
            [evidence[1], evidence[2]],
        )

    assert c4["checkpoint_count"] == 4


def test_transition_chain_extension_rejects_substituted_evidence() -> None:
    artifact, previous, previous_evidence, next_chain, next_evidence = _valid_extension()
    substituted = list(reversed(next_evidence))

    assert not verify_pilot_startup_evidence_checkpoint_transition_chain_extension(
        artifact,
        previous,
        previous_evidence,
        next_chain,
        substituted,
    )


def test_transition_chain_extension_rejects_tampering_authority_and_boolean_aliases() -> None:
    artifact, previous, previous_evidence, next_chain, next_evidence = _valid_extension()

    for key, value in (
        ("appended_transition_sha256", "f" * 64),
        ("extension_sha256", "0" * 64),
        ("production_deployment_authorized", True),
        ("previous_transition_count", True),
        ("next_transition_count", True),
    ):
        tampered = dict(artifact)
        tampered[key] = value
        assert not verify_pilot_startup_evidence_checkpoint_transition_chain_extension(
            tampered,
            previous,
            previous_evidence,
            next_chain,
            next_evidence,
        )


def test_transition_chain_extension_rejects_unexpected_fields() -> None:
    artifact, previous, previous_evidence, next_chain, next_evidence = _valid_extension()
    tampered = dict(artifact)
    tampered["externally_attested"] = True

    assert not verify_pilot_startup_evidence_checkpoint_transition_chain_extension(
        tampered,
        previous,
        previous_evidence,
        next_chain,
        next_evidence,
    )
