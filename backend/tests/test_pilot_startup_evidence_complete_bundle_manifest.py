from __future__ import annotations

from pathlib import Path

from app.pilot_startup_evidence_complete_bundle_manifest import (
    build_pilot_startup_evidence_complete_bundle_manifest,
    verify_pilot_startup_evidence_complete_bundle_manifest,
)
from test_pilot_startup_evidence_root_complete_graph import _build_fixture


def _build_complete_bundle(monkeypatch, tmp_path: Path):
    manifest, extension_chain, evidence, root_store, roots = _build_fixture(monkeypatch, tmp_path)
    bundle = build_pilot_startup_evidence_complete_bundle_manifest(
        manifest,
        extension_chain,
        evidence,
        root_store.root,
        *roots,
    )
    return manifest, extension_chain, evidence, root_store, roots, bundle


def test_complete_bundle_inventory_reaches_catalogs_and_receipts(monkeypatch, tmp_path: Path) -> None:
    manifest, extension_chain, evidence, root_store, roots, bundle = _build_complete_bundle(
        monkeypatch, tmp_path
    )

    inventory = bundle["artifact_digests"]
    assert len(inventory["catalogs"]) == 4
    assert inventory["startup_receipts"] == [character * 64 for character in "abcd"]
    assert bundle["artifact_count"] == sum(len(items) for items in inventory.values())
    assert bundle["production_deployment_authorized"] is False
    assert verify_pilot_startup_evidence_complete_bundle_manifest(
        bundle,
        manifest,
        extension_chain,
        evidence,
        root_store.root,
        *roots,
    )


def test_complete_bundle_inventory_is_deterministic(monkeypatch, tmp_path: Path) -> None:
    manifest, extension_chain, evidence, root_store, roots, bundle = _build_complete_bundle(
        monkeypatch, tmp_path
    )

    rebuilt = build_pilot_startup_evidence_complete_bundle_manifest(
        manifest,
        extension_chain,
        evidence,
        root_store.root,
        *roots,
    )
    assert rebuilt == bundle


def test_complete_bundle_verification_fails_when_referenced_receipt_disappears(
    monkeypatch, tmp_path: Path
) -> None:
    manifest, extension_chain, evidence, root_store, roots, bundle = _build_complete_bundle(
        monkeypatch, tmp_path
    )

    (roots[-1] / f"{'a' * 64}.json").unlink()
    assert not verify_pilot_startup_evidence_complete_bundle_manifest(
        bundle,
        manifest,
        extension_chain,
        evidence,
        root_store.root,
        *roots,
    )


def test_complete_bundle_verification_rejects_inventory_tampering(monkeypatch, tmp_path: Path) -> None:
    manifest, extension_chain, evidence, root_store, roots, bundle = _build_complete_bundle(
        monkeypatch, tmp_path
    )

    tampered = dict(bundle)
    tampered_inventory = {key: list(values) for key, values in bundle["artifact_digests"].items()}
    tampered_inventory["startup_receipts"] = ["f" * 64]
    tampered["artifact_digests"] = tampered_inventory
    tampered["artifact_count"] = sum(len(items) for items in tampered_inventory.values())

    assert not verify_pilot_startup_evidence_complete_bundle_manifest(
        tampered,
        manifest,
        extension_chain,
        evidence,
        root_store.root,
        *roots,
    )
