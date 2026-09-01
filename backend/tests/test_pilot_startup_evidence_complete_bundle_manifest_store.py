from __future__ import annotations

from pathlib import Path

import pytest

from app.pilot_startup_evidence_complete_bundle_manifest_store import (
    PilotStartupEvidenceCompleteBundleManifestStore,
)
from test_pilot_startup_evidence_complete_bundle_manifest import _build_complete_bundle


def _persist_complete_bundle(monkeypatch, tmp_path: Path):
    manifest, extension_chain, evidence, root_store, roots, bundle = _build_complete_bundle(
        monkeypatch, tmp_path
    )
    store = PilotStartupEvidenceCompleteBundleManifestStore(tmp_path / "complete-bundles")
    path = store.persist(
        bundle,
        manifest,
        extension_chain,
        evidence,
        root_store.root,
        *roots,
    )
    return manifest, extension_chain, evidence, root_store, roots, bundle, store, path


def test_complete_bundle_store_round_trip_reverifies_durable_closure(
    monkeypatch, tmp_path: Path
) -> None:
    manifest, extension_chain, evidence, root_store, roots, bundle, store, path = (
        _persist_complete_bundle(monkeypatch, tmp_path)
    )

    digest = bundle["complete_bundle_manifest_sha256"]
    assert path == store.path_for(digest)
    assert path.read_bytes() == store._canonical_bytes(bundle)
    assert store.load(
        digest,
        manifest,
        extension_chain,
        evidence,
        root_store.root,
        *roots,
    ) == bundle
    assert store.verify_durable_closure(
        digest,
        manifest,
        extension_chain,
        evidence,
        root_store.root,
        *roots,
    )


def test_complete_bundle_store_is_idempotent_for_identical_verified_bytes(
    monkeypatch, tmp_path: Path
) -> None:
    manifest, extension_chain, evidence, root_store, roots, bundle, store, path = (
        _persist_complete_bundle(monkeypatch, tmp_path)
    )

    second = store.persist(
        bundle,
        manifest,
        extension_chain,
        evidence,
        root_store.root,
        *roots,
    )
    assert second == path
    assert second.read_bytes() == store._canonical_bytes(bundle)


def test_complete_bundle_store_rejects_on_disk_tampering(monkeypatch, tmp_path: Path) -> None:
    manifest, extension_chain, evidence, root_store, roots, bundle, store, path = (
        _persist_complete_bundle(monkeypatch, tmp_path)
    )
    digest = bundle["complete_bundle_manifest_sha256"]
    path.write_bytes(b"{}\n")

    with pytest.raises(ValueError):
        store.load(
            digest,
            manifest,
            extension_chain,
            evidence,
            root_store.root,
            *roots,
        )
    with pytest.raises(ValueError, match="collision|tampering"):
        store.persist(
            bundle,
            manifest,
            extension_chain,
            evidence,
            root_store.root,
            *roots,
        )


def test_complete_bundle_store_fails_closed_when_referenced_receipt_disappears(
    monkeypatch, tmp_path: Path
) -> None:
    manifest, extension_chain, evidence, root_store, roots, bundle, store, _path = (
        _persist_complete_bundle(monkeypatch, tmp_path)
    )
    digest = bundle["complete_bundle_manifest_sha256"]
    (roots[-1] / f"{'a' * 64}.json").unlink()

    with pytest.raises(ValueError, match="durable graph verification"):
        store.load(
            digest,
            manifest,
            extension_chain,
            evidence,
            root_store.root,
            *roots,
        )
    assert not store.verify_durable_closure(
        digest,
        manifest,
        extension_chain,
        evidence,
        root_store.root,
        *roots,
    )


def test_complete_bundle_store_rejects_noncanonical_json(monkeypatch, tmp_path: Path) -> None:
    manifest, extension_chain, evidence, root_store, roots, bundle, store, path = (
        _persist_complete_bundle(monkeypatch, tmp_path)
    )
    digest = bundle["complete_bundle_manifest_sha256"]
    canonical = store._canonical_bytes(bundle).decode("utf-8")
    path.write_text("  " + canonical, encoding="utf-8")

    with pytest.raises(ValueError, match="canonical JSON"):
        store.load(
            digest,
            manifest,
            extension_chain,
            evidence,
            root_store.root,
            *roots,
        )


def test_complete_bundle_store_validates_digest_paths(tmp_path: Path) -> None:
    store = PilotStartupEvidenceCompleteBundleManifestStore(tmp_path / "complete-bundles")
    for invalid in ("", "A" * 64, "g" * 64, "0" * 63):
        with pytest.raises(ValueError):
            store.path_for(invalid)
