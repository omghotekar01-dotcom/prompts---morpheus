from __future__ import annotations

from copy import deepcopy

import pytest

from app.pilot_startup_evidence_checkpoint_chain import (
    build_pilot_startup_evidence_checkpoint_chain,
)
from app.pilot_startup_evidence_checkpoint_transition import (
    build_pilot_startup_evidence_checkpoint_transition,
)
from app.pilot_startup_evidence_checkpoint_transition_chain import (
    build_pilot_startup_evidence_checkpoint_transition_chain,
    verify_pilot_startup_evidence_checkpoint_transition_chain,
)


def _evidence():
    c1 = build_pilot_startup_evidence_checkpoint_chain(["a" * 64])
    c2 = build_pilot_startup_evidence_checkpoint_chain(["a" * 64, "b" * 64])
    c3 = build_pilot_startup_evidence_checkpoint_chain(["a" * 64, "b" * 64, "c" * 64])
    t1 = build_pilot_startup_evidence_checkpoint_transition(c1, c2)
    t2 = build_pilot_startup_evidence_checkpoint_transition(c2, c3)
    return [(t1, c1, c2), (t2, c2, c3)]


def test_transition_chain_is_deterministic_and_independently_verifiable() -> None:
    evidence = _evidence()
    first = build_pilot_startup_evidence_checkpoint_transition_chain(evidence)
    second = build_pilot_startup_evidence_checkpoint_transition_chain(evidence)

    assert first == second
    assert first["transition_count"] == 2
    assert first["starting_checkpoint_count"] == 1
    assert first["ending_checkpoint_count"] == 3
    assert first["transition_sha256_chain"] == [item[0]["transition_sha256"] for item in evidence]
    assert first["production_deployment_authorized"] is False
    assert verify_pilot_startup_evidence_checkpoint_transition_chain(first, evidence)


def test_transition_chain_rejects_replay_and_noncontiguous_sequence() -> None:
    evidence = _evidence()
    with pytest.raises(ValueError, match="replay"):
        build_pilot_startup_evidence_checkpoint_transition_chain([evidence[0], evidence[0]])

    c1 = evidence[0][1]
    c2 = evidence[0][2]
    fork = build_pilot_startup_evidence_checkpoint_chain(["a" * 64, "d" * 64])
    fork_transition = build_pilot_startup_evidence_checkpoint_transition(c1, fork)
    with pytest.raises(ValueError, match="contiguous"):
        build_pilot_startup_evidence_checkpoint_transition_chain(
            [evidence[0], (fork_transition, c1, fork)]
        )

    with pytest.raises(ValueError, match="contiguous"):
        build_pilot_startup_evidence_checkpoint_transition_chain(list(reversed(evidence)))


def test_transition_chain_rejects_inconsistent_shared_chain_evidence() -> None:
    evidence = _evidence()
    t2, _c2, c3 = evidence[1]
    wrong_c2 = deepcopy(evidence[0][2])
    wrong_c2["chain_sha256"] = "f" * 64

    with pytest.raises(ValueError, match="unverified transition"):
        build_pilot_startup_evidence_checkpoint_transition_chain(
            [evidence[0], (t2, wrong_c2, c3)]
        )


def test_transition_chain_verifier_rejects_tampering_authority_and_boolean_aliases() -> None:
    evidence = _evidence()
    artifact = build_pilot_startup_evidence_checkpoint_transition_chain(evidence)

    tampered = dict(artifact)
    tampered["production_deployment_authorized"] = True
    assert not verify_pilot_startup_evidence_checkpoint_transition_chain(tampered, evidence)

    tampered = dict(artifact)
    tampered["transition_count"] = True
    assert not verify_pilot_startup_evidence_checkpoint_transition_chain(tampered, evidence)

    tampered = dict(artifact)
    tampered["starting_checkpoint_count"] = True
    assert not verify_pilot_startup_evidence_checkpoint_transition_chain(tampered, evidence)

    tampered = dict(artifact)
    tampered["ending_chain_sha256"] = "f" * 64
    assert not verify_pilot_startup_evidence_checkpoint_transition_chain(tampered, evidence)


def test_transition_chain_verifier_rejects_reordered_or_substituted_evidence() -> None:
    evidence = _evidence()
    artifact = build_pilot_startup_evidence_checkpoint_transition_chain(evidence)

    assert not verify_pilot_startup_evidence_checkpoint_transition_chain(
        artifact, list(reversed(evidence))
    )
    assert not verify_pilot_startup_evidence_checkpoint_transition_chain(artifact, evidence[:1])


def test_transition_chain_verifier_rejects_unexpected_fields_and_digest_tampering() -> None:
    evidence = _evidence()
    artifact = build_pilot_startup_evidence_checkpoint_transition_chain(evidence)

    unexpected = dict(artifact)
    unexpected["production_ready"] = True
    assert not verify_pilot_startup_evidence_checkpoint_transition_chain(unexpected, evidence)

    tampered = dict(artifact)
    tampered["transition_chain_sha256"] = "0" * 64
    assert not verify_pilot_startup_evidence_checkpoint_transition_chain(tampered, evidence)


def test_transition_chain_requires_nonempty_verified_evidence() -> None:
    with pytest.raises(ValueError, match="at least one"):
        build_pilot_startup_evidence_checkpoint_transition_chain([])
