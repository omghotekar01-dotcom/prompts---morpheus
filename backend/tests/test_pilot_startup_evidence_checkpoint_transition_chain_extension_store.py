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
from app.pilot_startup_evidence_checkpoint_transition_chain_extension import (
    build_pilot_startup_evidence_checkpoint_transition_chain_extension,
)
from app.pilot_startup_evidence_checkpoint_transition_chain_extension_store import (
    PilotStartupEvidenceCheckpointTransitionChainExtensionStore,
)
from app.pilot_startup_evidence_checkpoint_transition_chain_store import (
    PilotStartupEvidenceCheckpointTransitionChainStore,
)
from app.pilot_startup_evidence_checkpoint_transition_store import (
    PilotStartupEvidenceCheckpointTransitionStore,
)


def _extension_evidence():
    c1 = build_pilot_startup_evidence_checkpoint_chain(["a" * 64])
    c2 = build_pilot_startup_evidence_checkpoint_chain(["a" * 64, "b" * 64])
    c3 = build_pilot_startup_evidence_checkpoint_chain(["a" * 64, "b" * 64, "c" * 64])
    t1 = build_pilot_startup_evidence_checkpoint_transition(c1, c2)
    t2 = build_pilot_startup_evidence_checkpoint_transition(c2, c3)
    e1 = (t1, c1, c2)
    e2 = (t2, c2, c3)
    previous_evidence = [e1]
    next_evidence = [e1, e2]
    previous_chain = build_pilot_startup_evidence_checkpoint_transition_chain(previous_evidence)
    next_chain = build_pilot_startup_evidence_checkpoint_transition_chain(next_evidence)
    extension = build_pilot_startup_evidence_checkpoint_transition_chain_extension(
        previous_chain,
        previous_evidence,
        next_chain,
        next_evidence,
    )
    return extension, previous_chain, previous_evidence, next_chain, next_evidence


def _persist_dependencies(tmp_path, previous_chain, previous_evidence, next_chain, next_evidence):
    checkpoint_chain_root = tmp_path / "checkpoint-chains"
    checkpoint_store = PilotStartupEvidenceCheckpointChainStore(checkpoint_chain_root)
    seen_checkpoint_chains: set[str] = set()
    for _transition, left, right in next_evidence:
        for checkpoint_chain in (left, right):
            digest = checkpoint_chain["chain_sha256"]
            if digest not in seen_checkpoint_chains:
                checkpoint_store.persist(checkpoint_chain)
                seen_checkpoint_chains.add(digest)

    transition_root = tmp_path / "transitions"
    transition_store = PilotStartupEvidenceCheckpointTransitionStore(transition_root)
    for transition, left, right in next_evidence:
        transition_store.persist(transition, left, right)

    transition_chain_root = tmp_path / "transition-chains"
    transition_chain_store = PilotStartupEvidenceCheckpointTransitionChainStore(transition_chain_root)
    transition_chain_store.persist(previous_chain, previous_evidence)
    transition_chain_store.persist(next_chain, next_evidence)
    return transition_chain_root, transition_root, checkpoint_chain_root


def test_extension_store_persists_loads_and_is_idempotent(tmp_path) -> None:
    extension, previous_chain, previous_evidence, next_chain, next_evidence = _extension_evidence()
    store = PilotStartupEvidenceCheckpointTransitionChainExtensionStore(tmp_path)

    first = store.persist(
        extension, previous_chain, previous_evidence, next_chain, next_evidence
    )
    second = store.persist(
        extension, previous_chain, previous_evidence, next_chain, next_evidence
    )

    assert first == second
    assert first.name == f'{extension["extension_sha256"]}.json'
    assert store.load(
        extension["extension_sha256"],
        previous_chain,
        previous_evidence,
        next_chain,
        next_evidence,
    ) == extension


def test_extension_store_verifies_against_nested_evidence_stores(tmp_path) -> None:
    extension, previous_chain, previous_evidence, next_chain, next_evidence = _extension_evidence()
    roots = _persist_dependencies(
        tmp_path, previous_chain, previous_evidence, next_chain, next_evidence
    )
    store = PilotStartupEvidenceCheckpointTransitionChainExtensionStore(tmp_path / "extensions")
    store.persist(extension, previous_chain, previous_evidence, next_chain, next_evidence)

    assert store.verify_against_evidence_stores(
        extension["extension_sha256"],
        previous_chain,
        previous_evidence,
        next_chain,
        next_evidence,
        *roots,
    )

    chain_store = PilotStartupEvidenceCheckpointTransitionChainStore(roots[0])
    chain_store.path_for(previous_chain["transition_chain_sha256"]).unlink()
    assert not store.verify_against_evidence_stores(
        extension["extension_sha256"],
        previous_chain,
        previous_evidence,
        next_chain,
        next_evidence,
        *roots,
    )


def test_extension_store_binding_detects_corrupted_nested_checkpoint_chain(tmp_path) -> None:
    extension, previous_chain, previous_evidence, next_chain, next_evidence = _extension_evidence()
    roots = _persist_dependencies(
        tmp_path, previous_chain, previous_evidence, next_chain, next_evidence
    )
    store = PilotStartupEvidenceCheckpointTransitionChainExtensionStore(tmp_path / "extensions")
    store.persist(extension, previous_chain, previous_evidence, next_chain, next_evidence)

    checkpoint_store = PilotStartupEvidenceCheckpointChainStore(roots[2])
    endpoint = next_evidence[-1][2]
    checkpoint_store.path_for(endpoint["chain_sha256"]).write_bytes(b"{}\n")

    assert not store.verify_against_evidence_stores(
        extension["extension_sha256"],
        previous_chain,
        previous_evidence,
        next_chain,
        next_evidence,
        *roots,
    )


def test_extension_store_rejects_authority_widening_and_boolean_aliases(tmp_path) -> None:
    extension, previous_chain, previous_evidence, next_chain, next_evidence = _extension_evidence()
    store = PilotStartupEvidenceCheckpointTransitionChainExtensionStore(tmp_path)

    for key, value in (
        ("production_deployment_authorized", True),
        ("previous_transition_count", True),
        ("next_transition_count", True),
    ):
        tampered = dict(extension)
        tampered[key] = value
        with pytest.raises(ValueError, match="failed verification"):
            store.persist(tampered, previous_chain, previous_evidence, next_chain, next_evidence)


def test_extension_store_detects_existing_file_tampering(tmp_path) -> None:
    extension, previous_chain, previous_evidence, next_chain, next_evidence = _extension_evidence()
    store = PilotStartupEvidenceCheckpointTransitionChainExtensionStore(tmp_path)
    path = store.persist(extension, previous_chain, previous_evidence, next_chain, next_evidence)
    path.write_bytes(b"{}\n")

    with pytest.raises(ValueError, match="collision or on-disk tampering"):
        store.persist(extension, previous_chain, previous_evidence, next_chain, next_evidence)
    with pytest.raises(ValueError):
        store.load(
            extension["extension_sha256"],
            previous_chain,
            previous_evidence,
            next_chain,
            next_evidence,
        )


def test_extension_store_rejects_noncanonical_json(tmp_path) -> None:
    extension, previous_chain, previous_evidence, next_chain, next_evidence = _extension_evidence()
    store = PilotStartupEvidenceCheckpointTransitionChainExtensionStore(tmp_path)
    path = store.path_for(extension["extension_sha256"])
    tmp_path.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(extension, indent=2, sort_keys=True).encode("utf-8") + b"\n")

    with pytest.raises(ValueError, match="not canonical JSON"):
        store.load(
            extension["extension_sha256"],
            previous_chain,
            previous_evidence,
            next_chain,
            next_evidence,
        )


def test_extension_store_rejects_malformed_and_traversal_digests(tmp_path) -> None:
    store = PilotStartupEvidenceCheckpointTransitionChainExtensionStore(tmp_path)

    for digest in ("a" * 63, "A" * 64, "../" + "a" * 64, "a" * 64 + "/x"):
        with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
            store.path_for(digest)


def test_extension_store_binding_rejects_substituted_or_reordered_evidence(tmp_path) -> None:
    extension, previous_chain, previous_evidence, next_chain, next_evidence = _extension_evidence()
    roots = _persist_dependencies(
        tmp_path, previous_chain, previous_evidence, next_chain, next_evidence
    )
    store = PilotStartupEvidenceCheckpointTransitionChainExtensionStore(tmp_path / "extensions")
    store.persist(extension, previous_chain, previous_evidence, next_chain, next_evidence)

    assert not store.verify_against_evidence_stores(
        extension["extension_sha256"],
        previous_chain,
        previous_evidence,
        next_chain,
        list(reversed(next_evidence)),
        *roots,
    )
