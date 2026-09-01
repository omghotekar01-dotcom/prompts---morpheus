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
from app.pilot_startup_evidence_checkpoint_transition_store import (
    PilotStartupEvidenceCheckpointTransitionStore,
)


def _chains() -> tuple[dict, dict]:
    previous = build_pilot_startup_evidence_checkpoint_chain(["a" * 64])
    next_chain = build_pilot_startup_evidence_checkpoint_chain(["a" * 64, "b" * 64])
    return previous, next_chain


def test_transition_store_persists_loads_and_is_idempotent(tmp_path) -> None:
    previous, next_chain = _chains()
    transition = build_pilot_startup_evidence_checkpoint_transition(previous, next_chain)
    store = PilotStartupEvidenceCheckpointTransitionStore(tmp_path / "transitions")

    first = store.persist(transition, previous, next_chain)
    second = store.persist(transition, previous, next_chain)

    assert first == second
    assert first.name == f'{transition["transition_sha256"]}.json'
    assert store.load(transition["transition_sha256"], previous, next_chain) == transition


def test_transition_store_verifies_against_persisted_chain_store(tmp_path) -> None:
    previous, next_chain = _chains()
    transition = build_pilot_startup_evidence_checkpoint_transition(previous, next_chain)
    chain_root = tmp_path / "chains"
    chain_store = PilotStartupEvidenceCheckpointChainStore(chain_root)
    chain_store.persist(previous)
    chain_store.persist(next_chain)

    store = PilotStartupEvidenceCheckpointTransitionStore(tmp_path / "transitions")
    store.persist(transition, previous, next_chain)

    assert store.verify_against_chain_store(transition["transition_sha256"], chain_root)

    chain_store.path_for(previous["chain_sha256"]).unlink()
    assert not store.verify_against_chain_store(transition["transition_sha256"], chain_root)


def test_transition_store_rejects_unverified_receipt_and_authority_widening(tmp_path) -> None:
    previous, next_chain = _chains()
    transition = build_pilot_startup_evidence_checkpoint_transition(previous, next_chain)
    store = PilotStartupEvidenceCheckpointTransitionStore(tmp_path)

    tampered = dict(transition)
    tampered["production_deployment_authorized"] = True
    with pytest.raises(ValueError, match="failed verification"):
        store.persist(tampered, previous, next_chain)

    tampered = dict(transition)
    tampered["previous_checkpoint_count"] = True
    with pytest.raises(ValueError, match="failed verification"):
        store.persist(tampered, previous, next_chain)


def test_transition_store_detects_existing_file_tampering(tmp_path) -> None:
    previous, next_chain = _chains()
    transition = build_pilot_startup_evidence_checkpoint_transition(previous, next_chain)
    store = PilotStartupEvidenceCheckpointTransitionStore(tmp_path)
    path = store.persist(transition, previous, next_chain)
    path.write_bytes(b"{}\n")

    with pytest.raises(ValueError, match="collision or on-disk tampering"):
        store.persist(transition, previous, next_chain)
    with pytest.raises(ValueError):
        store.load(transition["transition_sha256"], previous, next_chain)


def test_transition_store_rejects_noncanonical_json(tmp_path) -> None:
    previous, next_chain = _chains()
    transition = build_pilot_startup_evidence_checkpoint_transition(previous, next_chain)
    store = PilotStartupEvidenceCheckpointTransitionStore(tmp_path)
    path = store.path_for(transition["transition_sha256"])
    tmp_path.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(transition, indent=2, sort_keys=True).encode("utf-8") + b"\n")

    with pytest.raises(ValueError, match="not canonical JSON"):
        store.load(transition["transition_sha256"], previous, next_chain)


def test_transition_store_rejects_malformed_and_traversal_digests(tmp_path) -> None:
    store = PilotStartupEvidenceCheckpointTransitionStore(tmp_path)

    for digest in ("a" * 63, "A" * 64, "../" + "a" * 64, "a" * 64 + "/x"):
        with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
            store.path_for(digest)


def test_transition_store_binding_rejects_wrong_chain_artifact(tmp_path) -> None:
    previous, next_chain = _chains()
    transition = build_pilot_startup_evidence_checkpoint_transition(previous, next_chain)
    chain_root = tmp_path / "chains"
    chain_store = PilotStartupEvidenceCheckpointChainStore(chain_root)
    chain_store.persist(previous)
    chain_store.persist(next_chain)

    store = PilotStartupEvidenceCheckpointTransitionStore(tmp_path / "transitions")
    store.persist(transition, previous, next_chain)

    next_path = chain_store.path_for(next_chain["chain_sha256"])
    next_path.write_bytes(b"{}\n")
    assert not store.verify_against_chain_store(transition["transition_sha256"], chain_root)
