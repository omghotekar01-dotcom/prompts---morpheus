from __future__ import annotations

import json
from pathlib import Path

from app.pilot_startup_evidence_catalog import build_pilot_startup_evidence_catalog
from app.pilot_startup_evidence_catalog_store import PilotStartupEvidenceCatalogStore
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
from app.pilot_startup_evidence_root_manifest import build_pilot_startup_evidence_root_manifest, verify_pilot_startup_evidence_root_manifest_complete_graph
from app.pilot_startup_evidence_root_manifest_store import PilotStartupEvidenceRootManifestStore


def _write_receipt(root: Path, digest: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    payload = {"startup_evidence_sha256": digest}
    (root / f"{digest}.json").write_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n")


def _build_fixture(monkeypatch, tmp_path: Path):
    receipt_root = tmp_path / "startup-receipts"; catalog_root = tmp_path / "catalogs"
    catalog_store = PilotStartupEvidenceCatalogStore(catalog_root)
    monkeypatch.setattr("app.pilot_startup_evidence_store.verify_pilot_startup_evidence", lambda payload: True)
    catalog_digests: list[str] = []
    for index in range(4):
        _write_receipt(receipt_root, chr(97 + index) * 64)
        catalog = build_pilot_startup_evidence_catalog(receipt_root); catalog_store.persist(catalog)
        catalog_digests.append(catalog["catalog_sha256"])
    chains = [build_pilot_startup_evidence_checkpoint_chain(catalog_digests[:count]) for count in range(1, 5)]
    transitions = [build_pilot_startup_evidence_checkpoint_transition(chains[i], chains[i + 1]) for i in range(3)]
    transition_evidence = [(transitions[i], chains[i], chains[i + 1]) for i in range(3)]
    aggregate_evidence = [transition_evidence[:count] for count in range(1, 4)]
    aggregates = [build_pilot_startup_evidence_checkpoint_transition_chain(items) for items in aggregate_evidence]
    evidence = []
    for index in range(2):
        extension = build_pilot_startup_evidence_checkpoint_transition_chain_extension(aggregates[index], aggregate_evidence[index], aggregates[index + 1], aggregate_evidence[index + 1])
        evidence.append((extension, aggregates[index], aggregate_evidence[index], aggregates[index + 1], aggregate_evidence[index + 1]))
    extension_chain = build_pilot_startup_evidence_checkpoint_transition_chain_extension_chain(evidence)
    manifest = build_pilot_startup_evidence_root_manifest(extension_chain, evidence)
    checkpoint_chain_root = tmp_path / "checkpoint-chains"; transition_root = tmp_path / "transitions"; transition_chain_root = tmp_path / "transition-chains"; extension_root = tmp_path / "extensions"; extension_chain_root = tmp_path / "extension-chains"; root_manifest_root = tmp_path / "root-manifests"
    checkpoint_store = PilotStartupEvidenceCheckpointChainStore(checkpoint_chain_root); transition_store = PilotStartupEvidenceCheckpointTransitionStore(transition_root); transition_chain_store = PilotStartupEvidenceCheckpointTransitionChainStore(transition_chain_root); extension_store = PilotStartupEvidenceCheckpointTransitionChainExtensionStore(extension_root); extension_chain_store = PilotStartupEvidenceCheckpointTransitionChainExtensionChainStore(extension_chain_root)
    seen_checkpoint_chains: set[str] = set(); seen_transitions: set[str] = set(); seen_transition_chains: set[str] = set()
    for extension, previous_chain, previous_evidence, next_chain, next_evidence in evidence:
        for transition, left, right in next_evidence:
            for checkpoint_chain in (left, right):
                digest = checkpoint_chain["chain_sha256"]
                if digest not in seen_checkpoint_chains: checkpoint_store.persist(checkpoint_chain); seen_checkpoint_chains.add(digest)
            transition_digest = transition["transition_sha256"]
            if transition_digest not in seen_transitions: transition_store.persist(transition, left, right); seen_transitions.add(transition_digest)
        for transition_chain, items in ((previous_chain, previous_evidence), (next_chain, next_evidence)):
            digest = transition_chain["transition_chain_sha256"]
            if digest not in seen_transition_chains: transition_chain_store.persist(transition_chain, items); seen_transition_chains.add(digest)
        extension_store.persist(extension, previous_chain, previous_evidence, next_chain, next_evidence)
    extension_chain_store.persist(extension_chain, evidence)
    root_store = PilotStartupEvidenceRootManifestStore(root_manifest_root); root_store.persist(manifest, extension_chain, evidence)
    return manifest, extension_chain, evidence, root_store, (extension_chain_root, extension_root, transition_chain_root, transition_root, checkpoint_chain_root, catalog_root, receipt_root)


def test_complete_root_verification_reaches_catalogs_and_receipts(monkeypatch, tmp_path: Path) -> None:
    manifest, extension_chain, evidence, root_store, roots = _build_fixture(monkeypatch, tmp_path)
    assert verify_pilot_startup_evidence_root_manifest_complete_graph(manifest, extension_chain, evidence, *roots)
    assert root_store.verify_complete_evidence_graph(manifest["root_manifest_sha256"], extension_chain, evidence, *roots)


def test_complete_root_verification_fails_when_referenced_catalog_is_deleted(monkeypatch, tmp_path: Path) -> None:
    manifest, extension_chain, evidence, root_store, roots = _build_fixture(monkeypatch, tmp_path)
    first_catalog = evidence[0][2][0][1]["catalog_sha256_chain"][0]
    PilotStartupEvidenceCatalogStore(roots[-2]).path_for(first_catalog).unlink()
    assert not root_store.verify_complete_evidence_graph(manifest["root_manifest_sha256"], extension_chain, evidence, *roots)


def test_complete_root_verification_fails_when_referenced_receipt_is_deleted(monkeypatch, tmp_path: Path) -> None:
    manifest, extension_chain, evidence, root_store, roots = _build_fixture(monkeypatch, tmp_path)
    (roots[-1] / f"{'a' * 64}.json").unlink()
    assert not root_store.verify_complete_evidence_graph(manifest["root_manifest_sha256"], extension_chain, evidence, *roots)


def test_complete_root_verification_fails_when_referenced_receipt_is_corrupted(monkeypatch, tmp_path: Path) -> None:
    manifest, extension_chain, evidence, root_store, roots = _build_fixture(monkeypatch, tmp_path)
    (roots[-1] / f"{'b' * 64}.json").write_bytes(b"{}\n")
    assert not root_store.verify_complete_evidence_graph(manifest["root_manifest_sha256"], extension_chain, evidence, *roots)


def test_historical_catalogs_allow_later_extra_receipts(monkeypatch, tmp_path: Path) -> None:
    manifest, extension_chain, evidence, root_store, roots = _build_fixture(monkeypatch, tmp_path)
    _write_receipt(roots[-1], "e" * 64)
    assert root_store.verify_complete_evidence_graph(manifest["root_manifest_sha256"], extension_chain, evidence, *roots)
