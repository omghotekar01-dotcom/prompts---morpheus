from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.pilot_startup_evidence_catalog import build_pilot_startup_evidence_catalog
from app.pilot_startup_evidence_catalog_store import PilotStartupEvidenceCatalogStore


def test_catalog_checkpoint_persist_load_and_current_store_binding(tmp_path: Path) -> None:
    evidence_root = tmp_path / "evidence"
    checkpoint_root = tmp_path / "checkpoints"
    catalog = build_pilot_startup_evidence_catalog(evidence_root)
    store = PilotStartupEvidenceCatalogStore(checkpoint_root)

    first = store.persist(catalog)
    second = store.persist(catalog)
    assert first == second
    assert store.load(catalog["catalog_sha256"]) == catalog
    assert store.verify_against_evidence_store(catalog["catalog_sha256"], evidence_root)
    assert first.read_bytes().endswith(b"\n")
    assert b"\r\n" not in first.read_bytes()

    evidence_root.mkdir(parents=True, exist_ok=True)
    (evidence_root / "unexpected.txt").write_bytes(b"drift")
    assert not store.verify_against_evidence_store(catalog["catalog_sha256"], evidence_root)


def test_catalog_checkpoint_rejects_unverified_or_authority_widened_catalog(tmp_path: Path) -> None:
    catalog = build_pilot_startup_evidence_catalog(tmp_path / "evidence")
    store = PilotStartupEvidenceCatalogStore(tmp_path / "checkpoints")

    tampered = dict(catalog)
    tampered["production_deployment_authorized"] = True
    with pytest.raises(ValueError, match="failed verification"):
        store.persist(tampered)

    tampered = dict(catalog)
    tampered["receipt_count"] = True
    with pytest.raises(ValueError, match="failed verification"):
        store.persist(tampered)


def test_catalog_checkpoint_detects_collision_and_noncanonical_bytes(tmp_path: Path) -> None:
    catalog = build_pilot_startup_evidence_catalog(tmp_path / "evidence")
    store = PilotStartupEvidenceCatalogStore(tmp_path / "checkpoints")
    path = store.persist(catalog)

    path.write_bytes(b"{}\n")
    with pytest.raises(ValueError, match="collision|tampering"):
        store.persist(catalog)
    with pytest.raises(ValueError, match="filename does not match"):
        store.load(catalog["catalog_sha256"])

    path.write_bytes((json.dumps(catalog, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    with pytest.raises(ValueError, match="not canonical JSON"):
        store.load(catalog["catalog_sha256"])


def test_catalog_checkpoint_rejects_malformed_digest_and_path_traversal(tmp_path: Path) -> None:
    store = PilotStartupEvidenceCatalogStore(tmp_path)
    for value in ("", "a" * 63, "A" * 64, "../" + "a" * 64, "g" * 64):
        with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
            store.path_for(value)
