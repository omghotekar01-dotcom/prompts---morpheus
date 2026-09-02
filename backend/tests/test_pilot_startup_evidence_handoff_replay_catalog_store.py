from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.pilot_startup_evidence_handoff_replay_catalog import (
    build_pilot_startup_evidence_handoff_replay_catalog,
)
from app.pilot_startup_evidence_handoff_replay_catalog_store import (
    load_pilot_startup_evidence_handoff_replay_catalog,
    persist_pilot_startup_evidence_handoff_replay_catalog,
)
from test_pilot_startup_evidence_handoff_replay_catalog import _context


def test_replay_catalog_store_round_trip_is_idempotent(monkeypatch, tmp_path: Path) -> None:
    context, _descriptor = _context(monkeypatch, tmp_path)
    catalog = build_pilot_startup_evidence_handoff_replay_catalog([context])
    store = tmp_path / "replay-catalogs"

    path = persist_pilot_startup_evidence_handoff_replay_catalog(store, catalog, [context])
    repeated = persist_pilot_startup_evidence_handoff_replay_catalog(store, catalog, [context])

    assert path == repeated
    assert path.name == f"{catalog['replay_catalog_sha256']}.json"
    assert load_pilot_startup_evidence_handoff_replay_catalog(path, [context]) == catalog


def test_replay_catalog_store_rejects_on_disk_tamper(monkeypatch, tmp_path: Path) -> None:
    context, _descriptor = _context(monkeypatch, tmp_path)
    catalog = build_pilot_startup_evidence_handoff_replay_catalog([context])
    store = tmp_path / "replay-catalogs"
    path = persist_pilot_startup_evidence_handoff_replay_catalog(store, catalog, [context])
    path.write_bytes(b"{}")

    with pytest.raises(ValueError):
        load_pilot_startup_evidence_handoff_replay_catalog(path, [context])
    with pytest.raises(ValueError, match="collision|tampering"):
        persist_pilot_startup_evidence_handoff_replay_catalog(store, catalog, [context])


def test_replay_catalog_store_rejects_noncanonical_json(monkeypatch, tmp_path: Path) -> None:
    context, _descriptor = _context(monkeypatch, tmp_path)
    catalog = build_pilot_startup_evidence_handoff_replay_catalog([context])
    path = tmp_path / f"{catalog['replay_catalog_sha256']}.json"
    path.write_text(json.dumps(catalog, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="canonical"):
        load_pilot_startup_evidence_handoff_replay_catalog(path, [context])


def test_replay_catalog_store_rejects_filename_digest_substitution(
    monkeypatch, tmp_path: Path
) -> None:
    context, _descriptor = _context(monkeypatch, tmp_path)
    catalog = build_pilot_startup_evidence_handoff_replay_catalog([context])
    path = persist_pilot_startup_evidence_handoff_replay_catalog(
        tmp_path / "replay-catalogs", catalog, [context]
    )
    substituted = path.with_name(f"{'0' * 64}.json")
    path.rename(substituted)

    with pytest.raises(ValueError, match="filename/digest mismatch"):
        load_pilot_startup_evidence_handoff_replay_catalog(substituted, [context])


def test_replay_catalog_store_fails_closed_when_descriptor_changes(
    monkeypatch, tmp_path: Path
) -> None:
    context, _descriptor = _context(monkeypatch, tmp_path)
    catalog = build_pilot_startup_evidence_handoff_replay_catalog([context])
    path = persist_pilot_startup_evidence_handoff_replay_catalog(
        tmp_path / "replay-catalogs", catalog, [context]
    )
    Path(context.descriptor_path).write_bytes(b"{}")

    with pytest.raises(ValueError, match="fresh semantic verification"):
        load_pilot_startup_evidence_handoff_replay_catalog(path, [context])


def test_replay_catalog_store_fails_closed_when_transported_evidence_changes(
    monkeypatch, tmp_path: Path
) -> None:
    context, _descriptor = _context(monkeypatch, tmp_path)
    catalog = build_pilot_startup_evidence_handoff_replay_catalog([context])
    path = persist_pilot_startup_evidence_handoff_replay_catalog(
        tmp_path / "replay-catalogs", catalog, [context]
    )

    handoff = Path(context.bundle_dir)
    startup_receipts = sorted((handoff / "artifacts" / "startup_receipts").glob("*.json"))
    assert startup_receipts
    startup_receipts[0].write_bytes(b"{}")

    with pytest.raises(ValueError, match="fresh semantic verification"):
        load_pilot_startup_evidence_handoff_replay_catalog(path, [context])
