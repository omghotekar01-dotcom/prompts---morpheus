from __future__ import annotations

from copy import deepcopy

from app.pilot_startup_evidence_bundle_manifest import (
    build_pilot_startup_evidence_bundle_manifest,
    verify_pilot_startup_evidence_bundle_manifest,
    verify_pilot_startup_evidence_bundle_manifest_against_stores,
)
from app.pilot_startup_evidence_checkpoint_chain import build_pilot_startup_evidence_checkpoint_chain
from app.pilot_startup_evidence_checkpoint_chain_store import PilotStartupEvidenceCheckpointChainStore
from app.pilot_startup_evidence_checkpoint_transition import build_pilot_startup_evidence_checkpoint_transition
from app.pilot_startup_evidence_checkpoint_transition_chain import build_pilot_startup_evidence_checkpoint_transition_chain
from app.pilot_startup_evidence_checkpoint_transition_chain_extension import build_pilot_startup_evidence_checkpoint_transition_chain_extension
from app.pilot_startup_evidence_checkpoint_transition_chain_extension_chain import build_pilot_startup_evidence_checkpoint_transition_chain_extension_chain
from app.pilot_startup_evidence_checkpoint_transition_chain_extension_chain_store import PilotStartupEvidenceCheckpointTransitionChainExtensionChainStore
from app.pilot_startup_evidence_checkpoint_transition_chain_extension_store import PilotStartupEvidenceCheckpointTransitionChainExtensionStore
from app.pilot_startup_evidence_checkpoint_transition_chain_store import PilotStartupEvidenceCheckpointTransitionChainStore
from app.pilot_startup_evidence_checkpoint_transition_store import PilotStartupEvidenceCheckpointTransitionStore
from app.pilot_startup_evidence_root_manifest import build_pilot_startup_evidence_root_manifest
from app.pilot_startup_evidence_root_manifest_store import PilotStartupEvidenceRootManifestStore


def _fixture():
    chains = [
        build_pilot_startup_evidence_checkpoint_chain([chr(97 + j) * 64 for j in range(i)])
        for i in range(1, 5)
    ]
    transitions = [
        build_pilot_startup_evidence_checkpoint_transition(chains[i], chains[i + 1])
        for i in range(3)
    ]
    transition_evidence = [(transitions[i], chains[i], chains[i + 1]) for i in range(3)]
    aggregate_evidence = [transition_evidence[:i] for i in range(1, 4)]
    aggregates = [build_pilot_startup_evidence_checkpoint_transition_chain(items) for items in aggregate_evidence]
    evidence = []
    for i in range(2):
        extension = build_pilot_startup_evidence_checkpoint_transition_chain_extension(
            aggregates[i], aggregate_evidence[i], aggregates[i + 1], aggregate_evidence[i + 1]
        )
        evidence.append((extension, aggregates[i], aggregate_evidence[i], aggregates[i + 1], aggregate_evidence[i + 1]))
    extension_chain = build_pilot_startup_evidence_checkpoint_transition_chain_extension_chain(evidence)
    manifest = build_pilot_startup_evidence_root_manifest(extension_chain, evidence)
    return manifest, extension_chain, evidence


def _persist_graph(tmp_path, manifest, extension_chain, evidence):
    checkpoint_root = tmp_path / "checkpoint-chains"
    transition_root = tmp_path / "transitions"
    transition_chain_root = tmp_path / "transition-chains"
    extension_root = tmp_path / "extensions"
    extension_chain_root = tmp_path / "extension-chains"
    root_manifest_root = tmp_path / "root-manifests"

    checkpoint_store = PilotStartupEvidenceCheckpointChainStore(checkpoint_root)
    transition_store = PilotStartupEvidenceCheckpointTransitionStore(transition_root)
    transition_chain_store = PilotStartupEvidenceCheckpointTransitionChainStore(transition_chain_root)
    extension_store = PilotStartupEvidenceCheckpointTransitionChainExtensionStore(extension_root)
    extension_chain_store = PilotStartupEvidenceCheckpointTransitionChainExtensionChainStore(extension_chain_root)
    root_store = PilotStartupEvidenceRootManifestStore(root_manifest_root)

    seen_checkpoint: set[str] = set()
    seen_transition: set[str] = set()
    seen_transition_chain: set[str] = set()
    for extension, previous_chain, previous_evidence, next_chain, next_evidence in evidence:
        for transition, left, right in next_evidence:
            for checkpoint in (left, right):
                digest = checkpoint["chain_sha256"]
                if digest not in seen_checkpoint:
                    checkpoint_store.persist(checkpoint)
                    seen_checkpoint.add(digest)
            digest = transition["transition_sha256"]
            if digest not in seen_transition:
                transition_store.persist(transition, left, right)
                seen_transition.add(digest)
        for chain, chain_evidence in ((previous_chain, previous_evidence), (next_chain, next_evidence)):
            digest = chain["transition_chain_sha256"]
            if digest not in seen_transition_chain:
                transition_chain_store.persist(chain, chain_evidence)
                seen_transition_chain.add(digest)
        extension_store.persist(extension, previous_chain, previous_evidence, next_chain, next_evidence)

    extension_chain_store.persist(extension_chain, evidence)
    root_store.persist(manifest, extension_chain, evidence)
    return root_manifest_root, extension_chain_root, extension_root, transition_chain_root, transition_root, checkpoint_root


def test_bundle_manifest_is_deterministic_and_inventory_complete() -> None:
    manifest, extension_chain, evidence = _fixture()
    first = build_pilot_startup_evidence_bundle_manifest(manifest, extension_chain, evidence)
    second = build_pilot_startup_evidence_bundle_manifest(manifest, extension_chain, evidence)

    assert first == second
    assert first["production_deployment_authorized"] is False
    assert first["root_manifest_sha256"] == manifest["root_manifest_sha256"]
    assert first["artifact_count"] == sum(len(items) for items in first["artifact_digests"].values())
    assert verify_pilot_startup_evidence_bundle_manifest(first, manifest, extension_chain, evidence)


def test_bundle_manifest_rebinds_persisted_root_and_deep_evidence_graph(tmp_path) -> None:
    manifest, extension_chain, evidence = _fixture()
    bundle = build_pilot_startup_evidence_bundle_manifest(manifest, extension_chain, evidence)
    roots = _persist_graph(tmp_path, manifest, extension_chain, evidence)

    assert verify_pilot_startup_evidence_bundle_manifest_against_stores(
        bundle, manifest, extension_chain, evidence, *roots
    )

    checkpoint_store = PilotStartupEvidenceCheckpointChainStore(roots[-1])
    endpoint = evidence[-1][4][-1][2]
    checkpoint_store.path_for(endpoint["chain_sha256"]).write_bytes(b"{}\n")
    assert not verify_pilot_startup_evidence_bundle_manifest_against_stores(
        bundle, manifest, extension_chain, evidence, *roots
    )


def test_bundle_manifest_fails_if_persisted_root_is_missing(tmp_path) -> None:
    manifest, extension_chain, evidence = _fixture()
    bundle = build_pilot_startup_evidence_bundle_manifest(manifest, extension_chain, evidence)
    roots = _persist_graph(tmp_path, manifest, extension_chain, evidence)
    root_store = PilotStartupEvidenceRootManifestStore(roots[0])
    root_store.path_for(manifest["root_manifest_sha256"]).unlink()

    assert not verify_pilot_startup_evidence_bundle_manifest_against_stores(
        bundle, manifest, extension_chain, evidence, *roots
    )


def test_bundle_manifest_rejects_inventory_tampering_reordering_and_authority_widening() -> None:
    manifest, extension_chain, evidence = _fixture()
    bundle = build_pilot_startup_evidence_bundle_manifest(manifest, extension_chain, evidence)

    widened = deepcopy(bundle)
    widened["production_deployment_authorized"] = True
    assert not verify_pilot_startup_evidence_bundle_manifest(widened, manifest, extension_chain, evidence)

    bool_count = deepcopy(bundle)
    bool_count["artifact_count"] = True
    assert not verify_pilot_startup_evidence_bundle_manifest(bool_count, manifest, extension_chain, evidence)

    tampered = deepcopy(bundle)
    tampered["artifact_digests"]["checkpoint_chains"][0] = "f" * 64
    assert not verify_pilot_startup_evidence_bundle_manifest(tampered, manifest, extension_chain, evidence)

    reordered = deepcopy(bundle)
    reordered["artifact_digests"]["checkpoint_chains"] = list(reversed(reordered["artifact_digests"]["checkpoint_chains"]))
    assert not verify_pilot_startup_evidence_bundle_manifest(reordered, manifest, extension_chain, evidence)


def test_bundle_manifest_rejects_digest_tampering_extra_fields_and_substituted_evidence() -> None:
    manifest, extension_chain, evidence = _fixture()
    bundle = build_pilot_startup_evidence_bundle_manifest(manifest, extension_chain, evidence)

    digest_tampered = dict(bundle)
    digest_tampered["bundle_manifest_sha256"] = "0" * 64
    assert not verify_pilot_startup_evidence_bundle_manifest(digest_tampered, manifest, extension_chain, evidence)

    unexpected = dict(bundle)
    unexpected["externally_trusted"] = True
    assert not verify_pilot_startup_evidence_bundle_manifest(unexpected, manifest, extension_chain, evidence)

    substituted = deepcopy(evidence)
    substituted[0][0]["extension_sha256"] = "f" * 64
    assert not verify_pilot_startup_evidence_bundle_manifest(bundle, manifest, extension_chain, substituted)
