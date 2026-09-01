from __future__ import annotations

from pathlib import Path

import pytest

from app.pilot_startup_evidence_portable_handoff import (
    export_pilot_startup_evidence_portable_handoff,
    verify_pilot_startup_evidence_portable_handoff,
)
from test_pilot_startup_evidence_complete_bundle_manifest import _build_complete_bundle


def _export(monkeypatch, tmp_path: Path):
    manifest, extension_chain, evidence, root_store, roots, bundle = _build_complete_bundle(
        monkeypatch, tmp_path
    )
    path = export_pilot_startup_evidence_portable_handoff(
        bundle,
        manifest,
        extension_chain,
        evidence,
        tmp_path / "handoffs",
        root_store.root,
        *roots,
    )
    return manifest, extension_chain, evidence, root_store, roots, bundle, path


def test_portable_handoff_materializes_complete_inventory_and_self_verifies(
    monkeypatch, tmp_path: Path
) -> None:
    _manifest, _extension_chain, _evidence, _root_store, _roots, bundle, path = _export(
        monkeypatch, tmp_path
    )

    assert path.name == bundle["complete_bundle_manifest_sha256"]
    assert verify_pilot_startup_evidence_portable_handoff(path)
    expected = bundle["artifact_count"] + 2
    assert len([item for item in path.rglob("*") if item.is_file()]) == expected


def test_portable_handoff_is_idempotent_for_identical_verified_closure(
    monkeypatch, tmp_path: Path
) -> None:
    manifest, extension_chain, evidence, root_store, roots, bundle, path = _export(
        monkeypatch, tmp_path
    )
    before = (path / "handoff-manifest.json").read_bytes()

    second = export_pilot_startup_evidence_portable_handoff(
        bundle,
        manifest,
        extension_chain,
        evidence,
        tmp_path / "handoffs",
        root_store.root,
        *roots,
    )
    assert second == path
    assert (second / "handoff-manifest.json").read_bytes() == before


def test_portable_handoff_detects_copied_artifact_tampering(monkeypatch, tmp_path: Path) -> None:
    _manifest, _extension_chain, _evidence, _root_store, _roots, bundle, path = _export(
        monkeypatch, tmp_path
    )
    digest = bundle["artifact_digests"]["startup_receipts"][0]
    artifact = path / "artifacts" / "startup_receipts" / f"{digest}.json"
    artifact.write_bytes(b"{}\n")

    assert not verify_pilot_startup_evidence_portable_handoff(path)


def test_portable_handoff_rejects_missing_or_unexpected_files(monkeypatch, tmp_path: Path) -> None:
    _manifest, _extension_chain, _evidence, _root_store, _roots, bundle, path = _export(
        monkeypatch, tmp_path
    )
    digest = bundle["artifact_digests"]["catalogs"][0]
    artifact = path / "artifacts" / "catalogs" / f"{digest}.json"
    original = artifact.read_bytes()
    artifact.unlink()
    assert not verify_pilot_startup_evidence_portable_handoff(path)

    artifact.write_bytes(original)
    (path / "unexpected.txt").write_text("not inventoried", encoding="utf-8")
    assert not verify_pilot_startup_evidence_portable_handoff(path)


def test_portable_handoff_export_fails_closed_if_source_closure_is_incomplete(
    monkeypatch, tmp_path: Path
) -> None:
    manifest, extension_chain, evidence, root_store, roots, bundle = _build_complete_bundle(
        monkeypatch, tmp_path
    )
    (roots[-1] / f"{'a' * 64}.json").unlink()

    with pytest.raises(ValueError, match="durable-closure verification"):
        export_pilot_startup_evidence_portable_handoff(
            bundle,
            manifest,
            extension_chain,
            evidence,
            tmp_path / "handoffs",
            root_store.root,
            *roots,
        )
