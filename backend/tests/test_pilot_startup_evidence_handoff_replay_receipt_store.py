from __future__ import annotations

from pathlib import Path

import pytest

from app.pilot_startup_evidence_handoff_replay_receipt import (
    build_pilot_startup_evidence_handoff_replay_receipt,
)
from app.pilot_startup_evidence_handoff_replay_receipt_store import (
    load_pilot_startup_evidence_handoff_replay_receipt,
    persist_pilot_startup_evidence_handoff_replay_receipt,
)
from test_pilot_startup_evidence_portable_handoff import _export


def _receipt(monkeypatch, tmp_path: Path):
    manifest, extension_chain, evidence, _root_store, _roots, bundle, handoff = _export(
        monkeypatch, tmp_path
    )
    receipt = build_pilot_startup_evidence_handoff_replay_receipt(
        handoff, manifest, extension_chain, evidence
    )
    return manifest, extension_chain, evidence, bundle, handoff, receipt


def test_replay_receipt_store_round_trip_is_content_addressed_and_idempotent(
    monkeypatch, tmp_path: Path
) -> None:
    manifest, extension_chain, evidence, _bundle, handoff, receipt = _receipt(
        monkeypatch, tmp_path
    )
    store = tmp_path / "replay-receipts"

    first = persist_pilot_startup_evidence_handoff_replay_receipt(
        store, receipt, handoff, manifest, extension_chain, evidence
    )
    second = persist_pilot_startup_evidence_handoff_replay_receipt(
        store, receipt, handoff, manifest, extension_chain, evidence
    )

    assert first == second
    assert first.name == f"{receipt['replay_receipt_sha256']}.json"
    assert load_pilot_startup_evidence_handoff_replay_receipt(
        first, handoff, manifest, extension_chain, evidence
    ) == receipt


def test_replay_receipt_store_rejects_on_disk_tamper(monkeypatch, tmp_path: Path) -> None:
    manifest, extension_chain, evidence, _bundle, handoff, receipt = _receipt(
        monkeypatch, tmp_path
    )
    store = tmp_path / "replay-receipts"
    path = persist_pilot_startup_evidence_handoff_replay_receipt(
        store, receipt, handoff, manifest, extension_chain, evidence
    )
    path.write_bytes(b"{}")

    with pytest.raises(ValueError):
        persist_pilot_startup_evidence_handoff_replay_receipt(
            store, receipt, handoff, manifest, extension_chain, evidence
        )
    with pytest.raises(ValueError):
        load_pilot_startup_evidence_handoff_replay_receipt(
            path, handoff, manifest, extension_chain, evidence
        )


def test_replay_receipt_store_rejects_noncanonical_serialization(
    monkeypatch, tmp_path: Path
) -> None:
    manifest, extension_chain, evidence, _bundle, handoff, receipt = _receipt(
        monkeypatch, tmp_path
    )
    store = tmp_path / "replay-receipts"
    path = persist_pilot_startup_evidence_handoff_replay_receipt(
        store, receipt, handoff, manifest, extension_chain, evidence
    )
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="canonical"):
        load_pilot_startup_evidence_handoff_replay_receipt(
            path, handoff, manifest, extension_chain, evidence
        )


def test_replay_receipt_store_rejects_filename_digest_mismatch(
    monkeypatch, tmp_path: Path
) -> None:
    manifest, extension_chain, evidence, _bundle, handoff, receipt = _receipt(
        monkeypatch, tmp_path
    )
    store = tmp_path / "replay-receipts"
    path = persist_pilot_startup_evidence_handoff_replay_receipt(
        store, receipt, handoff, manifest, extension_chain, evidence
    )
    wrong = store / f"{'0' * 64}.json"
    wrong.write_bytes(path.read_bytes())

    with pytest.raises(ValueError, match="filename/digest"):
        load_pilot_startup_evidence_handoff_replay_receipt(
            wrong, handoff, manifest, extension_chain, evidence
        )


def test_replay_receipt_store_fails_closed_when_transported_evidence_changes(
    monkeypatch, tmp_path: Path
) -> None:
    manifest, extension_chain, evidence, bundle, handoff, receipt = _receipt(
        monkeypatch, tmp_path
    )
    store = tmp_path / "replay-receipts"
    path = persist_pilot_startup_evidence_handoff_replay_receipt(
        store, receipt, handoff, manifest, extension_chain, evidence
    )
    digest = bundle["artifact_digests"]["startup_receipts"][0]
    artifact = handoff / "artifacts" / "startup_receipts" / f"{digest}.json"
    artifact.write_bytes(b"{}")

    with pytest.raises(ValueError, match="semantic verification"):
        load_pilot_startup_evidence_handoff_replay_receipt(
            path, handoff, manifest, extension_chain, evidence
        )
