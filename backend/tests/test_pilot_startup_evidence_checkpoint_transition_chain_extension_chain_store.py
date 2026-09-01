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
from app.pilot_startup_evidence_checkpoint_transition_chain_extension_chain import (
    build_pilot_startup_evidence_checkpoint_transition_chain_extension_chain,
)
from app.pilot_startup_evidence_checkpoint_transition_chain_extension_chain_store import (
    PilotStartupEvidenceCheckpointTransitionChainExtensionChainStore,
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


def _fixture():
    chains = [
        build_pilot_startup_evidence_checkpoint_chain([chr(97 + j) * 64 for j in range(i)])
        for i in range(1, 5)
    ]
    transitions = [
        build_pilot_startup_evidence_checkpoint_transition(chains[i], chains[i + 1])
        for i in range(3)
    ]
    transition_evidence = [
        (transitions[i], chains[i], chains[i + 1]) for i in range(3)
    ]
    aggregate_evidence = [transition_evidence[:i] for i in range(1, 4)]
    aggregates = [
        build_pilot_startup_evidence_checkpoint_transition_chain(items)
        for items in aggregate_evidence
    ]

    evidence = []
    for i in range(2):
        extension = build_pilot_startup_evidence_checkpoint_transition_chain_extension(
            aggregates[i],
            aggregate_evidence[i],
            aggregates[i + 1],
            aggregate_evidence[i + 1],
        )
        evidence.append(
            (
                extension,
                aggregates[i],
                aggregate_evidence[i],
                aggregates[i + 1],
                aggregate_evidence[i + 1],
            )
        )

    artifact = build_pilot_startup_evidence_checkpoint_transition_chain_extension_chain(evidence)
    return artifact, evidence


def _persist_dependencies(tmp_path, evidence):
    checkpoint_chain_root = tmp_path / "checkpoint-chains"
    transition_root = tmp_path / "transitions"
    transition_chain_root = tmp_path / "transition-chains"
    extension_root = tmp_path / "extensions"

    checkpoint_store = PilotStartupEvidenceCheckpointChainStore(checkpoint_chain_root)
    transition_store = PilotStartupEvidenceCheckpointTransitionStore(transition_root)
    transition_chain_store = PilotStartupEvidenceCheckpointTransitionChainStore(
        transition_chain_root
    )
    extension_store = PilotStartupEvidenceCheckpointTransitionChainExtensionStore(
        extension_root
    )

    seen_checkpoint_chains: set[str] = set()
    seen_transitions: set[str] = set()
    seen_transition_chains: set[str] = set()

    for extension, previous_chain, previous_evidence, next_chain, next_evidence in evidence:
        for transition, left, right in next_evidence:
            for checkpoint_chain in (left, right):
                digest = checkpoint_chain["chain_sha256"]
                if digest not in seen_checkpoint_chains:
                    checkpoint_store.persist(checkpoint_chain)
                    seen_checkpoint_chains.add(digest)

            transition_digest = transition["transition_sha256"]
            if transition_digest not in seen_transitions:
                transition_store.persist(transition, left, right)
                seen_transitions.add(transition_digest)

        for transition_chain, transition_chain_evidence in (
            (previous_chain, previous_evidence),
            (next_chain, next_evidence),
        ):
            digest = transition_chain["transition_chain_sha256"]
            if digest not in seen_transition_chains:
                transition_chain_store.persist(transition_chain, transition_chain_evidence)
                seen_transition_chains.add(digest)

        extension_store.persist(
            extension,
            previous_chain,
            previous_evidence,
            next_chain,
            next_evidence,
        )

    return extension_root, transition_chain_root, transition_root, checkpoint_chain_root


def test_extension_chain_store_persists_loads_and_is_idempotent(tmp_path) -> None:
    artifact, evidence = _fixture()
    store = PilotStartupEvidenceCheckpointTransitionChainExtensionChainStore(tmp_path)

    first = store.persist(artifact, evidence)
    second = store.persist(artifact, evidence)

    assert first == second
    assert first.name == f'{artifact["extension_chain_sha256"]}.json'
    assert store.load(artifact["extension_chain_sha256"], evidence) == artifact


def test_extension_chain_store_verifies_against_all_nested_evidence_stores(tmp_path) -> None:
    artifact, evidence = _fixture()
    roots = _persist_dependencies(tmp_path, evidence)
    store = PilotStartupEvidenceCheckpointTransitionChainExtensionChainStore(
        tmp_path / "extension-chains"
    )
    store.persist(artifact, evidence)

    assert store.verify_against_evidence_stores(
        artifact["extension_chain_sha256"],
        evidence,
        *roots,
    )

    extension_store = PilotStartupEvidenceCheckpointTransitionChainExtensionStore(roots[0])
    extension_store.path_for(evidence[0][0]["extension_sha256"]).unlink()
    assert not store.verify_against_evidence_stores(
        artifact["extension_chain_sha256"],
        evidence,
        *roots,
    )


def test_extension_chain_store_binding_detects_corrupted_deep_checkpoint(tmp_path) -> None:
    artifact, evidence = _fixture()
    roots = _persist_dependencies(tmp_path, evidence)
    store = PilotStartupEvidenceCheckpointTransitionChainExtensionChainStore(
        tmp_path / "extension-chains"
    )
    store.persist(artifact, evidence)

    checkpoint_store = PilotStartupEvidenceCheckpointChainStore(roots[3])
    endpoint = evidence[-1][4][-1][2]
    checkpoint_store.path_for(endpoint["chain_sha256"]).write_bytes(b"{}\n")

    assert not store.verify_against_evidence_stores(
        artifact["extension_chain_sha256"],
        evidence,
        *roots,
    )


def test_extension_chain_store_rejects_authority_widening_and_boolean_aliases(tmp_path) -> None:
    artifact, evidence = _fixture()
    store = PilotStartupEvidenceCheckpointTransitionChainExtensionChainStore(tmp_path)

    for key, value in (
        ("production_deployment_authorized", True),
        ("extension_count", True),
        ("starting_transition_count", True),
        ("ending_transition_count", True),
    ):
        tampered = dict(artifact)
        tampered[key] = value
        with pytest.raises(ValueError, match="failed verification"):
            store.persist(tampered, evidence)


def test_extension_chain_store_detects_existing_file_tampering(tmp_path) -> None:
    artifact, evidence = _fixture()
    store = PilotStartupEvidenceCheckpointTransitionChainExtensionChainStore(tmp_path)
    path = store.persist(artifact, evidence)
    path.write_bytes(b"{}\n")

    with pytest.raises(ValueError, match="collision or on-disk tampering"):
        store.persist(artifact, evidence)
    with pytest.raises(ValueError):
        store.load(artifact["extension_chain_sha256"], evidence)


def test_extension_chain_store_rejects_noncanonical_json(tmp_path) -> None:
    artifact, evidence = _fixture()
    store = PilotStartupEvidenceCheckpointTransitionChainExtensionChainStore(tmp_path)
    path = store.path_for(artifact["extension_chain_sha256"])
    tmp_path.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(artifact, indent=2, sort_keys=True).encode("utf-8") + b"\n")

    with pytest.raises(ValueError, match="not canonical JSON"):
        store.load(artifact["extension_chain_sha256"], evidence)


def test_extension_chain_store_rejects_malformed_and_traversal_digests(tmp_path) -> None:
    store = PilotStartupEvidenceCheckpointTransitionChainExtensionChainStore(tmp_path)

    for digest in ("a" * 63, "A" * 64, "../" + "a" * 64, "a" * 64 + "/x"):
        with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
            store.path_for(digest)


def test_extension_chain_store_binding_rejects_reordered_or_substituted_evidence(tmp_path) -> None:
    artifact, evidence = _fixture()
    roots = _persist_dependencies(tmp_path, evidence)
    store = PilotStartupEvidenceCheckpointTransitionChainExtensionChainStore(
        tmp_path / "extension-chains"
    )
    store.persist(artifact, evidence)

    assert not store.verify_against_evidence_stores(
        artifact["extension_chain_sha256"],
        list(reversed(evidence)),
        *roots,
    )

    substituted = list(evidence)
    first = list(substituted[0])
    first[0] = dict(first[0])
    first[0]["extension_sha256"] = "f" * 64
    substituted[0] = tuple(first)
    assert not store.verify_against_evidence_stores(
        artifact["extension_chain_sha256"],
        substituted,
        *roots,
    )
