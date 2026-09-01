from __future__ import annotations

import json

import pytest

from app.pilot_startup_evidence_checkpoint_chain import (
    build_pilot_startup_evidence_checkpoint_chain,
)
from app.pilot_startup_evidence_checkpoint_chain_store import (
    PilotStartupEvidenceCheckpointChainStore,
)
from app.pilot_startup_evidence_checkpoint_transition import (
    build_pilot_startup_evidence_checkpoint_transition,
)
from app.pilot_startup_evidence_checkpoint_transition_chain import (
    build_pilot_startup_evidence_checkpoint_transition_chain,
)
from app.pilot_startup_evidence_checkpoint_transition_chain_store import (
    PilotStartupEvidenceCheckpointTransitionChainStore,
)
from app.pilot_startup_evidence_checkpoint_transition_store import (
    PilotStartupEvidenceCheckpointTransitionStore,
)


def _evidence():
    c1 = build_pilot_startup_evidence_checkpoint_chain(["a" * 64])
    c2 = build_pilot_startup_evidence_checkpoint_chain(["a" * 64, "b" * 64])
    c3 = build_pilot_startup_evidence_checkpoint_chain(["a" * 64, "b" * 64, "c" * 64])
    t1 = build_pilot_startup_evidence_checkpoint_transition(c1, c2)
    t2 = build_pilot_startup_evidence_checkpoint_transition(c2, c3)
    return [(t1, c1, c2), (t2, c2, c3)]


def _persist_dependencies(tmp_path, evidence):
    checkpoint_chain_root = tmp_path / "checkpoint-chains"
    checkpoint_chain_store = PilotStartupEvidenceCheckpointChainStore(checkpoint_chain_root)
    seen_chains: set[str] = set()
    for _transition, previous_chain, next_chain in evidence:
        for chain in (previous_chain, next_chain):
            digest = chain["chain_sha256"]
            if digest not in seen_chains:
                checkpoint_chain_store.persist(chain)
                seen_chains.add(digest)

    transition_root = tmp_path / "transitions"
    transition_store = PilotStartupEvidenceCheckpointTransitionStore(transition_root)
    for transition, previous_chain, next_chain in evidence:
        transition_store.persist(transition, previous_chain, next_chain)
    return transition_root, checkpoint_chain_root


def test_transition_chain_store_persists_loads_and_is_idempotent(tmp_path) -> None:
    evidence = _evidence()
    artifact = build_pilot_startup_evidence_checkpoint_transition_chain(evidence)
    store = PilotStartupEvidenceCheckpointTransitionChainStore(tmp_path / "transition-chains")

    first = store.persist(artifact, evidence)
    second = store.persist(artifact, evidence)

    assert first == second
    assert first.name == f'{artifact["transition_chain_sha256"]}.json'
    assert store.load(artifact["transition_chain_sha256"], evidence) == artifact


def test_transition_chain_store_verifies_against_nested_evidence_stores(tmp_path) -> None:
    evidence = _evidence()
    artifact = build_pilot_startup_evidence_checkpoint_transition_chain(evidence)
    transition_root, checkpoint_chain_root = _persist_dependencies(tmp_path, evidence)
    store = PilotStartupEvidenceCheckpointTransitionChainStore(tmp_path / "transition-chains")
    store.persist(artifact, evidence)

    assert store.verify_against_evidence_stores(
        artifact["transition_chain_sha256"],
        evidence,
        transition_root,
        checkpoint_chain_root,
    )

    transition_store = PilotStartupEvidenceCheckpointTransitionStore(transition_root)
    transition_store.path_for(evidence[1][0]["transition_sha256"]).unlink()
    assert not store.verify_against_evidence_stores(
        artifact["transition_chain_sha256"],
        evidence,
        transition_root,
        checkpoint_chain_root,
    )


def test_transition_chain_store_binding_detects_corrupted_checkpoint_chain(tmp_path) -> None:
    evidence = _evidence()
    artifact = build_pilot_startup_evidence_checkpoint_transition_chain(evidence)
    transition_root, checkpoint_chain_root = _persist_dependencies(tmp_path, evidence)
    store = PilotStartupEvidenceCheckpointTransitionChainStore(tmp_path / "transition-chains")
    store.persist(artifact, evidence)

    checkpoint_store = PilotStartupEvidenceCheckpointChainStore(checkpoint_chain_root)
    endpoint = evidence[-1][2]
    checkpoint_store.path_for(endpoint["chain_sha256"]).write_bytes(b"{}\n")

    assert not store.verify_against_evidence_stores(
        artifact["transition_chain_sha256"],
        evidence,
        transition_root,
        checkpoint_chain_root,
    )


def test_transition_chain_store_rejects_authority_widening_and_boolean_aliases(tmp_path) -> None:
    evidence = _evidence()
    artifact = build_pilot_startup_evidence_checkpoint_transition_chain(evidence)
    store = PilotStartupEvidenceCheckpointTransitionChainStore(tmp_path)

    tampered = dict(artifact)
    tampered["production_deployment_authorized"] = True
    with pytest.raises(ValueError, match="failed verification"):
        store.persist(tampered, evidence)

    tampered = dict(artifact)
    tampered["transition_count"] = True
    with pytest.raises(ValueError, match="failed verification"):
        store.persist(tampered, evidence)


def test_transition_chain_store_detects_existing_file_tampering(tmp_path) -> None:
    evidence = _evidence()
    artifact = build_pilot_startup_evidence_checkpoint_transition_chain(evidence)
    store = PilotStartupEvidenceCheckpointTransitionChainStore(tmp_path)
    path = store.persist(artifact, evidence)
    path.write_bytes(b"{}\n")

    with pytest.raises(ValueError, match="collision or on-disk tampering"):
        store.persist(artifact, evidence)
    with pytest.raises(ValueError):
        store.load(artifact["transition_chain_sha256"], evidence)


def test_transition_chain_store_rejects_noncanonical_json(tmp_path) -> None:
    evidence = _evidence()
    artifact = build_pilot_startup_evidence_checkpoint_transition_chain(evidence)
    store = PilotStartupEvidenceCheckpointTransitionChainStore(tmp_path)
    path = store.path_for(artifact["transition_chain_sha256"])
    tmp_path.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(artifact, indent=2, sort_keys=True).encode("utf-8") + b"\n")

    with pytest.raises(ValueError, match="not canonical JSON"):
        store.load(artifact["transition_chain_sha256"], evidence)


def test_transition_chain_store_rejects_malformed_and_traversal_digests(tmp_path) -> None:
    store = PilotStartupEvidenceCheckpointTransitionChainStore(tmp_path)

    for digest in ("a" * 63, "A" * 64, "../" + "a" * 64, "a" * 64 + "/x"):
        with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
            store.path_for(digest)


def test_transition_chain_store_binding_rejects_substituted_evidence(tmp_path) -> None:
    evidence = _evidence()
    artifact = build_pilot_startup_evidence_checkpoint_transition_chain(evidence)
    transition_root, checkpoint_chain_root = _persist_dependencies(tmp_path, evidence)
    store = PilotStartupEvidenceCheckpointTransitionChainStore(tmp_path / "transition-chains")
    store.persist(artifact, evidence)

    assert not store.verify_against_evidence_stores(
        artifact["transition_chain_sha256"],
        list(reversed(evidence)),
        transition_root,
        checkpoint_chain_root,
    )
