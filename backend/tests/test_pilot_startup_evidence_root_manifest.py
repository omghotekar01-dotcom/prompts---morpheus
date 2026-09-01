from __future__ import annotations

import json
from copy import deepcopy

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
from app.pilot_startup_evidence_root_manifest import (
    build_pilot_startup_evidence_root_manifest,
    verify_pilot_startup_evidence_root_manifest,
    verify_pilot_startup_evidence_root_manifest_against_stores,
)
from app.pilot_startup_evidence_root_manifest_store import (
    PilotStartupEvidenceRootManifestStore,
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

    extension_chain = (
        build_pilot_startup_evidence_checkpoint_transition_chain_extension_chain(evidence)
    )
    return extension_chain, evidence


def _persist_graph(tmp_path, extension_chain, evidence):
    checkpoint_chain_root = tmp_path / "checkpoint-chains"
    transition_root = tmp_path / "transitions"
    transition_chain_root = tmp_path / "transition-chains"
    extension_root = tmp_path / "extensions"
    extension_chain_root = tmp_path / "extension-chains"

    checkpoint_store = PilotStartupEvidenceCheckpointChainStore(checkpoint_chain_root)
    transition_store = PilotStartupEvidenceCheckpointTransitionStore(transition_root)
    transition_chain_store = PilotStartupEvidenceCheckpointTransitionChainStore(
        transition_chain_root
    )
    extension_store = PilotStartupEvidenceCheckpointTransitionChainExtensionStore(extension_root)
    extension_chain_store = PilotStartupEvidenceCheckpointTransitionChainExtensionChainStore(
        extension_chain_root
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

    extension_chain_store.persist(extension_chain, evidence)
    return (
        extension_chain_root,
        extension_root,
        transition_chain_root,
        transition_root,
        checkpoint_chain_root,
    )


def test_root_manifest_is_deterministic_and_binds_verified_extension_chain() -> None:
    extension_chain, evidence = _fixture()

    first = build_pilot_startup_evidence_root_manifest(extension_chain, evidence)
    second = build_pilot_startup_evidence_root_manifest(extension_chain, evidence)

    assert first == second
    assert first["extension_chain_sha256"] == extension_chain["extension_chain_sha256"]
    assert first["production_deployment_authorized"] is False
    assert verify_pilot_startup_evidence_root_manifest(first, extension_chain, evidence)


def test_root_manifest_verifies_full_immutable_store_graph(tmp_path) -> None:
    extension_chain, evidence = _fixture()
    manifest = build_pilot_startup_evidence_root_manifest(extension_chain, evidence)
    roots = _persist_graph(tmp_path, extension_chain, evidence)

    assert verify_pilot_startup_evidence_root_manifest_against_stores(
        manifest, extension_chain, evidence, *roots
    )

    checkpoint_store = PilotStartupEvidenceCheckpointChainStore(roots[-1])
    endpoint = evidence[-1][4][-1][2]
    checkpoint_store.path_for(endpoint["chain_sha256"]).write_bytes(b"{}\n")

    assert not verify_pilot_startup_evidence_root_manifest_against_stores(
        manifest, extension_chain, evidence, *roots
    )


def test_root_manifest_rejects_authority_widening_boolean_aliases_and_extra_fields() -> None:
    extension_chain, evidence = _fixture()
    manifest = build_pilot_startup_evidence_root_manifest(extension_chain, evidence)

    for key, value in (
        ("production_deployment_authorized", True),
        ("extension_count", True),
        ("starting_transition_count", True),
        ("ending_transition_count", True),
    ):
        tampered = dict(manifest)
        tampered[key] = value
        assert not verify_pilot_startup_evidence_root_manifest(
            tampered, extension_chain, evidence
        )

    unexpected = dict(manifest)
    unexpected["externally_trusted"] = True
    assert not verify_pilot_startup_evidence_root_manifest(
        unexpected, extension_chain, evidence
    )


def test_root_manifest_rejects_digest_binding_tampering_and_substituted_evidence() -> None:
    extension_chain, evidence = _fixture()
    manifest = build_pilot_startup_evidence_root_manifest(extension_chain, evidence)

    tampered = dict(manifest)
    tampered["ending_transition_chain_sha256"] = "f" * 64
    assert not verify_pilot_startup_evidence_root_manifest(
        tampered, extension_chain, evidence
    )

    digest_tampered = dict(manifest)
    digest_tampered["root_manifest_sha256"] = "0" * 64
    assert not verify_pilot_startup_evidence_root_manifest(
        digest_tampered, extension_chain, evidence
    )

    substituted = deepcopy(evidence)
    substituted[0][0]["extension_sha256"] = "f" * 64
    assert not verify_pilot_startup_evidence_root_manifest(
        manifest, extension_chain, substituted
    )


def test_root_manifest_store_binding_fails_if_top_level_chain_is_missing(tmp_path) -> None:
    extension_chain, evidence = _fixture()
    manifest = build_pilot_startup_evidence_root_manifest(extension_chain, evidence)
    roots = _persist_graph(tmp_path, extension_chain, evidence)

    chain_store = PilotStartupEvidenceCheckpointTransitionChainExtensionChainStore(roots[0])
    chain_store.path_for(extension_chain["extension_chain_sha256"]).unlink()

    assert not verify_pilot_startup_evidence_root_manifest_against_stores(
        manifest, extension_chain, evidence, *roots
    )


def test_root_manifest_store_persists_loads_and_is_idempotent(tmp_path) -> None:
    extension_chain, evidence = _fixture()
    manifest = build_pilot_startup_evidence_root_manifest(extension_chain, evidence)
    store = PilotStartupEvidenceRootManifestStore(tmp_path / "root-manifests")

    path = store.persist(manifest, extension_chain, evidence)

    assert path == store.path_for(manifest["root_manifest_sha256"])
    assert store.persist(manifest, extension_chain, evidence) == path
    assert store.load(manifest["root_manifest_sha256"], extension_chain, evidence) == manifest


def test_root_manifest_store_rebinds_full_nested_evidence_graph(tmp_path) -> None:
    extension_chain, evidence = _fixture()
    manifest = build_pilot_startup_evidence_root_manifest(extension_chain, evidence)
    roots = _persist_graph(tmp_path, extension_chain, evidence)
    store = PilotStartupEvidenceRootManifestStore(tmp_path / "root-manifests")
    store.persist(manifest, extension_chain, evidence)

    assert store.verify_against_evidence_stores(
        manifest["root_manifest_sha256"], extension_chain, evidence, *roots
    )

    checkpoint_store = PilotStartupEvidenceCheckpointChainStore(roots[-1])
    endpoint = evidence[-1][4][-1][2]
    checkpoint_store.path_for(endpoint["chain_sha256"]).write_bytes(b"{}\n")

    assert not store.verify_against_evidence_stores(
        manifest["root_manifest_sha256"], extension_chain, evidence, *roots
    )


def test_root_manifest_store_rejects_invalid_authority_and_boolean_aliases(tmp_path) -> None:
    extension_chain, evidence = _fixture()
    manifest = build_pilot_startup_evidence_root_manifest(extension_chain, evidence)
    store = PilotStartupEvidenceRootManifestStore(tmp_path / "root-manifests")

    for key, value in (
        ("production_deployment_authorized", True),
        ("extension_count", True),
        ("starting_transition_count", True),
        ("ending_transition_count", True),
    ):
        tampered = dict(manifest)
        tampered[key] = value
        with pytest.raises(ValueError):
            store.persist(tampered, extension_chain, evidence)


def test_root_manifest_store_detects_tampering_and_noncanonical_json(tmp_path) -> None:
    extension_chain, evidence = _fixture()
    manifest = build_pilot_startup_evidence_root_manifest(extension_chain, evidence)
    store = PilotStartupEvidenceRootManifestStore(tmp_path / "root-manifests")
    path = store.persist(manifest, extension_chain, evidence)

    path.write_bytes(b"{}\n")
    with pytest.raises(ValueError):
        store.load(manifest["root_manifest_sha256"], extension_chain, evidence)
    with pytest.raises(ValueError):
        store.persist(manifest, extension_chain, evidence)

    path.write_bytes((json.dumps(manifest, indent=2, ensure_ascii=True) + "\n").encode("utf-8"))
    with pytest.raises(ValueError, match="canonical JSON"):
        store.load(manifest["root_manifest_sha256"], extension_chain, evidence)


def test_root_manifest_store_rejects_malformed_and_traversal_digests(tmp_path) -> None:
    store = PilotStartupEvidenceRootManifestStore(tmp_path / "root-manifests")

    for digest in (
        "0" * 63,
        "0" * 65,
        "A" * 64,
        "../" + "0" * 61,
        "0" * 63 + "/",
    ):
        with pytest.raises(ValueError):
            store.path_for(digest)
