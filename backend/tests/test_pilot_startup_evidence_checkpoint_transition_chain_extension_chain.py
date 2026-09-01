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
)
from app.pilot_startup_evidence_checkpoint_transition_chain_extension_chain import (
    build_pilot_startup_evidence_checkpoint_transition_chain_extension_chain,
    verify_pilot_startup_evidence_checkpoint_transition_chain_extension_chain,
)


def _fixture():
    chains = [
        build_pilot_startup_evidence_checkpoint_chain([chr(97 + j) * 64 for j in range(i)])
        for i in range(1, 6)
    ]
    transitions = [
        build_pilot_startup_evidence_checkpoint_transition(chains[i], chains[i + 1])
        for i in range(4)
    ]
    transition_evidence = [
        (transitions[i], chains[i], chains[i + 1]) for i in range(4)
    ]
    aggregate_evidence = [transition_evidence[:i] for i in range(1, 5)]
    aggregates = [
        build_pilot_startup_evidence_checkpoint_transition_chain(items)
        for items in aggregate_evidence
    ]

    extensions = []
    for i in range(3):
        artifact = build_pilot_startup_evidence_checkpoint_transition_chain_extension(
            aggregates[i],
            aggregate_evidence[i],
            aggregates[i + 1],
            aggregate_evidence[i + 1],
        )
        extensions.append(
            (
                artifact,
                aggregates[i],
                aggregate_evidence[i],
                aggregates[i + 1],
                aggregate_evidence[i + 1],
            )
        )
    return extensions


def test_extension_chain_is_deterministic_and_independently_verifiable() -> None:
    evidence = _fixture()[:2]
    artifact = build_pilot_startup_evidence_checkpoint_transition_chain_extension_chain(evidence)
    rebuilt = build_pilot_startup_evidence_checkpoint_transition_chain_extension_chain(evidence)

    assert rebuilt == artifact
    assert artifact["extension_count"] == 2
    assert artifact["starting_transition_count"] == 1
    assert artifact["ending_transition_count"] == 3
    assert artifact["production_deployment_authorized"] is False
    assert verify_pilot_startup_evidence_checkpoint_transition_chain_extension_chain(
        artifact, evidence
    )


def test_extension_chain_rejects_replay() -> None:
    first = _fixture()[0]
    with pytest.raises(ValueError, match="non-replayed contiguous"):
        build_pilot_startup_evidence_checkpoint_transition_chain_extension_chain([first, first])


def test_extension_chain_rejects_reordering() -> None:
    evidence = _fixture()[:2]
    with pytest.raises(ValueError, match="non-replayed contiguous"):
        build_pilot_startup_evidence_checkpoint_transition_chain_extension_chain(
            list(reversed(evidence))
        )


def test_extension_chain_rejects_individually_valid_but_noncontiguous_gap() -> None:
    evidence = _fixture()
    with pytest.raises(ValueError, match="non-replayed contiguous"):
        build_pilot_startup_evidence_checkpoint_transition_chain_extension_chain(
            [evidence[0], evidence[2]]
        )


def test_extension_chain_rejects_tampering_authority_and_boolean_aliases() -> None:
    evidence = _fixture()[:2]
    artifact = build_pilot_startup_evidence_checkpoint_transition_chain_extension_chain(evidence)

    for key, value in (
        ("extension_chain_sha256", "0" * 64),
        ("starting_transition_chain_sha256", "f" * 64),
        ("production_deployment_authorized", True),
        ("extension_count", True),
        ("starting_transition_count", True),
        ("ending_transition_count", True),
    ):
        tampered = dict(artifact)
        tampered[key] = value
        assert not verify_pilot_startup_evidence_checkpoint_transition_chain_extension_chain(
            tampered, evidence
        )


def test_extension_chain_rejects_substituted_evidence_and_unexpected_fields() -> None:
    evidence = _fixture()[:2]
    artifact = build_pilot_startup_evidence_checkpoint_transition_chain_extension_chain(evidence)

    assert not verify_pilot_startup_evidence_checkpoint_transition_chain_extension_chain(
        artifact, [evidence[1]]
    )

    unexpected = dict(artifact)
    unexpected["trusted_timestamp"] = True
    assert not verify_pilot_startup_evidence_checkpoint_transition_chain_extension_chain(
        unexpected, evidence
    )


def test_extension_chain_requires_nonempty_evidence() -> None:
    with pytest.raises(ValueError, match="non-replayed contiguous"):
        build_pilot_startup_evidence_checkpoint_transition_chain_extension_chain([])
