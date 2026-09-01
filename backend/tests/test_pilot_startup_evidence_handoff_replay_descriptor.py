from __future__ import annotations

from pathlib import Path

from app.pilot_startup_evidence_handoff_replay_descriptor import (
    build_pilot_startup_evidence_handoff_replay_descriptor,
    verify_pilot_startup_evidence_handoff_replay_descriptor,
)
from app.pilot_startup_evidence_handoff_replay_receipt import (
    build_pilot_startup_evidence_handoff_replay_receipt,
)
from app.pilot_startup_evidence_handoff_replay_receipt_store import (
    persist_pilot_startup_evidence_handoff_replay_receipt,
)
from test_pilot_startup_evidence_portable_handoff import _export


def _descriptor(monkeypatch, tmp_path: Path):
    manifest, extension_chain, evidence, _root_store, _roots, bundle, handoff = _export(
        monkeypatch, tmp_path
    )
    receipt = build_pilot_startup_evidence_handoff_replay_receipt(
        handoff, manifest, extension_chain, evidence
    )
    receipt_path = persist_pilot_startup_evidence_handoff_replay_receipt(
        tmp_path / "replay-receipts", receipt, handoff, manifest, extension_chain, evidence
    )
    descriptor = build_pilot_startup_evidence_handoff_replay_descriptor(
        receipt_path, handoff, manifest, extension_chain, evidence
    )
    return manifest, extension_chain, evidence, bundle, handoff, receipt_path, descriptor


def test_replay_descriptor_is_deterministic_and_freshly_verifiable(monkeypatch, tmp_path: Path) -> None:
    manifest, extension_chain, evidence, _bundle, handoff, receipt_path, descriptor = _descriptor(
        monkeypatch, tmp_path
    )
    rebuilt = build_pilot_startup_evidence_handoff_replay_descriptor(
        receipt_path, handoff, manifest, extension_chain, evidence
    )

    assert descriptor == rebuilt
    assert descriptor["semantic_replay_required"] is True
    assert descriptor["production_deployment_authorized"] is False
    assert verify_pilot_startup_evidence_handoff_replay_descriptor(
        descriptor, receipt_path, handoff, manifest, extension_chain, evidence
    )


def test_replay_descriptor_rejects_descriptor_tamper(monkeypatch, tmp_path: Path) -> None:
    manifest, extension_chain, evidence, _bundle, handoff, receipt_path, descriptor = _descriptor(
        monkeypatch, tmp_path
    )
    tampered = dict(descriptor)
    tampered["semantic_replay_required"] = False

    assert not verify_pilot_startup_evidence_handoff_replay_descriptor(
        tampered, receipt_path, handoff, manifest, extension_chain, evidence
    )


def test_replay_descriptor_fails_closed_when_persisted_receipt_is_tampered(
    monkeypatch, tmp_path: Path
) -> None:
    manifest, extension_chain, evidence, _bundle, handoff, receipt_path, descriptor = _descriptor(
        monkeypatch, tmp_path
    )
    receipt_path.write_bytes(b"{}")

    assert not verify_pilot_startup_evidence_handoff_replay_descriptor(
        descriptor, receipt_path, handoff, manifest, extension_chain, evidence
    )


def test_replay_descriptor_fails_closed_when_transported_evidence_changes(
    monkeypatch, tmp_path: Path
) -> None:
    manifest, extension_chain, evidence, bundle, handoff, receipt_path, descriptor = _descriptor(
        monkeypatch, tmp_path
    )
    digest = bundle["artifact_digests"]["startup_receipts"][0]
    artifact = handoff / "artifacts" / "startup_receipts" / f"{digest}.json"
    artifact.write_bytes(b"{}")

    assert not verify_pilot_startup_evidence_handoff_replay_descriptor(
        descriptor, receipt_path, handoff, manifest, extension_chain, evidence
    )
