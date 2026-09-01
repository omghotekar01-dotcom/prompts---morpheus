from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.pilot_startup_evidence_handoff_replay_descriptor_store import (
    load_pilot_startup_evidence_handoff_replay_descriptor,
    persist_pilot_startup_evidence_handoff_replay_descriptor,
)
from test_pilot_startup_evidence_handoff_replay_descriptor import _descriptor


def test_replay_descriptor_store_round_trip_is_idempotent(monkeypatch, tmp_path: Path) -> None:
    manifest, extension_chain, evidence, _bundle, handoff, receipt_path, descriptor = _descriptor(
        monkeypatch, tmp_path
    )
    store = tmp_path / "replay-descriptors"

    path = persist_pilot_startup_evidence_handoff_replay_descriptor(
        store, descriptor, receipt_path, handoff, manifest, extension_chain, evidence
    )
    repeated = persist_pilot_startup_evidence_handoff_replay_descriptor(
        store, descriptor, receipt_path, handoff, manifest, extension_chain, evidence
    )

    assert path == repeated
    assert path.name == f"{descriptor['replay_descriptor_sha256']}.json"
    assert load_pilot_startup_evidence_handoff_replay_descriptor(
        path, receipt_path, handoff, manifest, extension_chain, evidence
    ) == descriptor


def test_replay_descriptor_store_rejects_on_disk_tamper(monkeypatch, tmp_path: Path) -> None:
    manifest, extension_chain, evidence, _bundle, handoff, receipt_path, descriptor = _descriptor(
        monkeypatch, tmp_path
    )
    store = tmp_path / "replay-descriptors"
    path = persist_pilot_startup_evidence_handoff_replay_descriptor(
        store, descriptor, receipt_path, handoff, manifest, extension_chain, evidence
    )
    path.write_bytes(b"{}")

    with pytest.raises(ValueError):
        load_pilot_startup_evidence_handoff_replay_descriptor(
            path, receipt_path, handoff, manifest, extension_chain, evidence
        )
    with pytest.raises(ValueError):
        persist_pilot_startup_evidence_handoff_replay_descriptor(
            store, descriptor, receipt_path, handoff, manifest, extension_chain, evidence
        )


def test_replay_descriptor_store_rejects_noncanonical_json(monkeypatch, tmp_path: Path) -> None:
    manifest, extension_chain, evidence, _bundle, handoff, receipt_path, descriptor = _descriptor(
        monkeypatch, tmp_path
    )
    path = tmp_path / f"{descriptor['replay_descriptor_sha256']}.json"
    path.write_text(json.dumps(descriptor, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="canonical"):
        load_pilot_startup_evidence_handoff_replay_descriptor(
            path, receipt_path, handoff, manifest, extension_chain, evidence
        )


def test_replay_descriptor_store_rejects_filename_digest_substitution(
    monkeypatch, tmp_path: Path
) -> None:
    manifest, extension_chain, evidence, _bundle, handoff, receipt_path, descriptor = _descriptor(
        monkeypatch, tmp_path
    )
    store = tmp_path / "replay-descriptors"
    path = persist_pilot_startup_evidence_handoff_replay_descriptor(
        store, descriptor, receipt_path, handoff, manifest, extension_chain, evidence
    )
    substituted = path.with_name(f"{'0' * 64}.json")
    path.rename(substituted)

    with pytest.raises(ValueError, match="filename/digest mismatch"):
        load_pilot_startup_evidence_handoff_replay_descriptor(
            substituted, receipt_path, handoff, manifest, extension_chain, evidence
        )


def test_replay_descriptor_store_fails_closed_when_receipt_changes(monkeypatch, tmp_path: Path) -> None:
    manifest, extension_chain, evidence, _bundle, handoff, receipt_path, descriptor = _descriptor(
        monkeypatch, tmp_path
    )
    path = persist_pilot_startup_evidence_handoff_replay_descriptor(
        tmp_path / "replay-descriptors",
        descriptor,
        receipt_path,
        handoff,
        manifest,
        extension_chain,
        evidence,
    )
    receipt_path.write_bytes(b"{}")

    with pytest.raises(ValueError, match="fresh semantic verification"):
        load_pilot_startup_evidence_handoff_replay_descriptor(
            path, receipt_path, handoff, manifest, extension_chain, evidence
        )


def test_replay_descriptor_store_fails_closed_when_transported_evidence_changes(
    monkeypatch, tmp_path: Path
) -> None:
    manifest, extension_chain, evidence, bundle, handoff, receipt_path, descriptor = _descriptor(
        monkeypatch, tmp_path
    )
    path = persist_pilot_startup_evidence_handoff_replay_descriptor(
        tmp_path / "replay-descriptors",
        descriptor,
        receipt_path,
        handoff,
        manifest,
        extension_chain,
        evidence,
    )
    digest = bundle["artifact_digests"]["startup_receipts"][0]
    artifact = handoff / "artifacts" / "startup_receipts" / f"{digest}.json"
    artifact.write_bytes(b"{}")

    with pytest.raises(ValueError, match="fresh semantic verification"):
        load_pilot_startup_evidence_handoff_replay_descriptor(
            path, receipt_path, handoff, manifest, extension_chain, evidence
        )
