from __future__ import annotations

import json
from copy import deepcopy

import pytest

from app.pilot_startup_evidence_bundle_manifest import build_pilot_startup_evidence_bundle_manifest
from app.pilot_startup_evidence_bundle_manifest_store import PilotStartupEvidenceBundleManifestStore
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
    transitions = [build_pilot_startup_evidence_checkpoint_transition(chains[i], chains[i + 1]) for i in range(3)]
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
    bundle = build_pilot_startup_evidence_bundle_manifest(manifest, extension_chain, evidence)
    return bundle, manifest, extension_chain, evidence


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


def test_bundle_store_persists_loads_and_is_idempotent(tmp_path) -> None:
    bundle, manifest, extension_chain, evidence = _fixture()
    store = PilotStartupEvidenceBundleManifestStore(tmp_path / "bundle-manifests")

    path = store.persist(bundle, manifest, extension_chain, evidence)
    assert path == store.path_for(bundle["bundle_manifest_sha256"])
    assert store.persist(bundle, manifest, extension_chain, evidence) == path
    assert store.load(bundle["bundle_manifest_sha256"], manifest, extension_chain, evidence) == bundle


def test_bundle_store_rebinds_complete_nested_evidence_graph(tmp_path) -> None:
    bundle, manifest, extension_chain, evidence = _fixture()
    roots = _persist_graph(tmp_path, manifest, extension_chain, evidence)
    store = PilotStartupEvidenceBundleManifestStore(tmp_path / "bundle-manifests")
    store.persist(bundle, manifest, extension_chain, evidence)

    assert store.verify_against_evidence_stores(
        bundle["bundle_manifest_sha256"], manifest, extension_chain, evidence, *roots
    )

    checkpoint_store = PilotStartupEvidenceCheckpointChainStore(roots[-1])
    endpoint = evidence[-1][4][-1][2]
    checkpoint_store.path_for(endpoint["chain_sha256"]).write_bytes(b"{}\n")
    assert not store.verify_against_evidence_stores(
        bundle["bundle_manifest_sha256"], manifest, extension_chain, evidence, *roots
    )


def test_bundle_store_fails_if_persisted_root_is_missing(tmp_path) -> None:
    bundle, manifest, extension_chain, evidence = _fixture()
    roots = _persist_graph(tmp_path, manifest, extension_chain, evidence)
    store = PilotStartupEvidenceBundleManifestStore(tmp_path / "bundle-manifests")
    store.persist(bundle, manifest, extension_chain, evidence)
    root_store = PilotStartupEvidenceRootManifestStore(roots[0])
    root_store.path_for(manifest["root_manifest_sha256"]).unlink()

    assert not store.verify_against_evidence_stores(
        bundle["bundle_manifest_sha256"], manifest, extension_chain, evidence, *roots
    )


def test_bundle_store_rejects_authority_widening_boolean_alias_and_substitution(tmp_path) -> None:
    bundle, manifest, extension_chain, evidence = _fixture()
    store = PilotStartupEvidenceBundleManifestStore(tmp_path / "bundle-manifests")

    widened = deepcopy(bundle)
    widened["production_deployment_authorized"] = True
    with pytest.raises(ValueError):
        store.persist(widened, manifest, extension_chain, evidence)

    bool_count = deepcopy(bundle)
    bool_count["artifact_count"] = True
    with pytest.raises(ValueError):
        store.persist(bool_count, manifest, extension_chain, evidence)

    substituted = deepcopy(bundle)
    substituted["artifact_digests"]["checkpoint_chains"][0] = "f" * 64
    with pytest.raises(ValueError):
        store.persist(substituted, manifest, extension_chain, evidence)


def test_bundle_store_detects_tampering_and_noncanonical_json(tmp_path) -> None:
    bundle, manifest, extension_chain, evidence = _fixture()
    store = PilotStartupEvidenceBundleManifestStore(tmp_path / "bundle-manifests")
    path = store.persist(bundle, manifest, extension_chain, evidence)

    path.write_bytes(b"{}\n")
    with pytest.raises(ValueError):
        store.load(bundle["bundle_manifest_sha256"], manifest, extension_chain, evidence)
    with pytest.raises(ValueError):
        store.persist(bundle, manifest, extension_chain, evidence)

    path.write_bytes((json.dumps(bundle, indent=2, ensure_ascii=True) + "\n").encode("utf-8"))
    with pytest.raises(ValueError, match="canonical JSON"):
        store.load(bundle["bundle_manifest_sha256"], manifest, extension_chain, evidence)


def test_bundle_store_rejects_malformed_and_traversal_digests(tmp_path) -> None:
    store = PilotStartupEvidenceBundleManifestStore(tmp_path / "bundle-manifests")
    for digest in ("0" * 63, "0" * 65, "A" * 64, "../" + "0" * 61, "0" * 63 + "/"):
        with pytest.raises(ValueError):
            store.path_for(digest)
