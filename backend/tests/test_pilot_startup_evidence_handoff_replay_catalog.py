from __future__ import annotations

from pathlib import Path

import pytest

from app.pilot_startup_evidence_handoff_replay_catalog import (
    ReplayDescriptorContext,
    build_pilot_startup_evidence_handoff_replay_catalog,
    verify_pilot_startup_evidence_handoff_replay_catalog,
)
from app.pilot_startup_evidence_handoff_replay_descriptor_store import (
    persist_pilot_startup_evidence_handoff_replay_descriptor,
)
from test_pilot_startup_evidence_handoff_replay_descriptor import _descriptor


def _context(monkeypatch, tmp_path: Path) -> tuple[ReplayDescriptorContext, dict]:
    manifest, extension_chain, evidence, _bundle, handoff, receipt_path, descriptor = _descriptor(
        monkeypatch, tmp_path
    )
    descriptor_path = persist_pilot_startup_evidence_handoff_replay_descriptor(
        tmp_path / "replay-descriptors",
        descriptor,
        receipt_path,
        handoff,
        manifest,
        extension_chain,
        evidence,
    )
    return (
        ReplayDescriptorContext(
            descriptor_path=descriptor_path,
            receipt_path=receipt_path,
            bundle_dir=handoff,
            manifest=manifest,
            extension_chain=extension_chain,
            evidence=evidence,
        ),
        descriptor,
    )


def test_replay_catalog_builds_deterministically_from_freshly_verified_descriptor(
    monkeypatch, tmp_path: Path
) -> None:
    context, descriptor = _context(monkeypatch, tmp_path)

    first = build_pilot_startup_evidence_handoff_replay_catalog([context])
    second = build_pilot_startup_evidence_handoff_replay_catalog([context])

    assert first == second
    assert first["descriptor_count"] == 1
    assert first["descriptor_entries"][0]["replay_descriptor_sha256"] == descriptor[
        "replay_descriptor_sha256"
    ]
    assert first["semantic_replay_required"] is True
    assert first["production_deployment_authorized"] is False
    assert verify_pilot_startup_evidence_handoff_replay_catalog(first, [context])


def test_replay_catalog_rejects_empty_or_duplicate_inventory(monkeypatch, tmp_path: Path) -> None:
    context, _descriptor_payload = _context(monkeypatch, tmp_path)

    with pytest.raises(ValueError, match="at least one"):
        build_pilot_startup_evidence_handoff_replay_catalog([])
    with pytest.raises(ValueError, match="duplicate"):
        build_pilot_startup_evidence_handoff_replay_catalog([context, context])


def test_replay_catalog_rejects_catalog_tampering(monkeypatch, tmp_path: Path) -> None:
    context, _descriptor_payload = _context(monkeypatch, tmp_path)
    catalog = build_pilot_startup_evidence_handoff_replay_catalog([context])
    tampered = dict(catalog)
    tampered["descriptor_count"] = 2

    assert not verify_pilot_startup_evidence_handoff_replay_catalog(tampered, [context])


def test_replay_catalog_fails_closed_when_persisted_descriptor_changes(
    monkeypatch, tmp_path: Path
) -> None:
    context, _descriptor_payload = _context(monkeypatch, tmp_path)
    catalog = build_pilot_startup_evidence_handoff_replay_catalog([context])
    Path(context.descriptor_path).write_bytes(b"{}")

    assert not verify_pilot_startup_evidence_handoff_replay_catalog(catalog, [context])


def test_replay_catalog_fails_closed_when_transported_evidence_changes(
    monkeypatch, tmp_path: Path
) -> None:
    context, _descriptor_payload = _context(monkeypatch, tmp_path)
    catalog = build_pilot_startup_evidence_handoff_replay_catalog([context])

    handoff = Path(context.bundle_dir)
    startup_receipts = sorted((handoff / "artifacts" / "startup_receipts").glob("*.json"))
    assert startup_receipts
    startup_receipts[0].write_bytes(b"{}")

    assert not verify_pilot_startup_evidence_handoff_replay_catalog(catalog, [context])
