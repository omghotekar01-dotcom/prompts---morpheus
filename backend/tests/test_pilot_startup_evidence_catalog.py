from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.pilot_startup_evidence_catalog import (
    build_pilot_startup_evidence_catalog,
    verify_pilot_startup_evidence_catalog,
    verify_pilot_startup_evidence_catalog_against_store,
)


def _write_receipt(root: Path, digest: str) -> None:
    payload = {"startup_evidence_sha256": digest}
    (root / f"{digest}.json").write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def test_catalog_is_deterministic_and_store_bound(monkeypatch, tmp_path: Path) -> None:
    first = "a" * 64
    second = "b" * 64
    _write_receipt(tmp_path, second)
    _write_receipt(tmp_path, first)
    monkeypatch.setattr("app.pilot_startup_evidence_store.verify_pilot_startup_evidence", lambda payload: True)

    catalog = build_pilot_startup_evidence_catalog(tmp_path)
    assert catalog["receipt_count"] == 2
    assert catalog["receipt_digests"] == [first, second]
    assert verify_pilot_startup_evidence_catalog(catalog)
    assert verify_pilot_startup_evidence_catalog_against_store(catalog, tmp_path)
    assert catalog == build_pilot_startup_evidence_catalog(tmp_path)
    assert catalog["production_deployment_authorized"] is False


def test_catalog_detects_receipt_addition_and_omission(monkeypatch, tmp_path: Path) -> None:
    first = "a" * 64
    second = "b" * 64
    _write_receipt(tmp_path, first)
    monkeypatch.setattr("app.pilot_startup_evidence_store.verify_pilot_startup_evidence", lambda payload: True)
    catalog = build_pilot_startup_evidence_catalog(tmp_path)

    _write_receipt(tmp_path, second)
    assert not verify_pilot_startup_evidence_catalog_against_store(catalog, tmp_path)

    (tmp_path / f"{second}.json").unlink()
    assert verify_pilot_startup_evidence_catalog_against_store(catalog, tmp_path)
    (tmp_path / f"{first}.json").unlink()
    assert not verify_pilot_startup_evidence_catalog_against_store(catalog, tmp_path)


def test_catalog_rejects_unexpected_entries_and_corrupt_receipts(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.pilot_startup_evidence_store.verify_pilot_startup_evidence", lambda payload: True)
    (tmp_path / "notes.txt").write_text("unexpected", encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected entry"):
        build_pilot_startup_evidence_catalog(tmp_path)

    (tmp_path / "notes.txt").unlink()
    digest = "a" * 64
    (tmp_path / f"{digest}.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="filename does not match"):
        build_pilot_startup_evidence_catalog(tmp_path)


def test_catalog_verifier_rejects_tampering_and_boolean_count(monkeypatch, tmp_path: Path) -> None:
    digest = "a" * 64
    _write_receipt(tmp_path, digest)
    monkeypatch.setattr("app.pilot_startup_evidence_store.verify_pilot_startup_evidence", lambda payload: True)
    catalog = build_pilot_startup_evidence_catalog(tmp_path)

    tampered = dict(catalog)
    tampered["receipt_count"] = True
    assert not verify_pilot_startup_evidence_catalog(tampered)

    tampered = dict(catalog)
    tampered["production_deployment_authorized"] = True
    assert not verify_pilot_startup_evidence_catalog(tampered)

    tampered = dict(catalog)
    tampered["receipt_digests"] = ["b" * 64]
    assert not verify_pilot_startup_evidence_catalog(tampered)
