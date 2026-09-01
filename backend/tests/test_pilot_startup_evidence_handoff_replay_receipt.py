from __future__ import annotations

from pathlib import Path

from app.pilot_startup_evidence_handoff_replay_receipt import (
    build_pilot_startup_evidence_handoff_replay_receipt,
    verify_pilot_startup_evidence_handoff_replay_receipt,
)
from test_pilot_startup_evidence_portable_handoff import _export


def test_handoff_replay_receipt_is_deterministic_and_freshly_verifiable(
    monkeypatch, tmp_path: Path
) -> None:
    manifest, extension_chain, evidence, _root_store, _roots, _bundle, path = _export(
        monkeypatch, tmp_path
    )

    first = build_pilot_startup_evidence_handoff_replay_receipt(
        path, manifest, extension_chain, evidence
    )
    second = build_pilot_startup_evidence_handoff_replay_receipt(
        path, manifest, extension_chain, evidence
    )

    assert first == second
    assert first["semantic_replay_passed"] is True
    assert first["production_deployment_authorized"] is False
    assert verify_pilot_startup_evidence_handoff_replay_receipt(
        first, path, manifest, extension_chain, evidence
    )


def test_handoff_replay_receipt_rejects_receipt_tamper(monkeypatch, tmp_path: Path) -> None:
    manifest, extension_chain, evidence, _root_store, _roots, _bundle, path = _export(
        monkeypatch, tmp_path
    )
    receipt = build_pilot_startup_evidence_handoff_replay_receipt(
        path, manifest, extension_chain, evidence
    )
    tampered = dict(receipt)
    tampered["semantic_replay_passed"] = False

    assert not verify_pilot_startup_evidence_handoff_replay_receipt(
        tampered, path, manifest, extension_chain, evidence
    )


def test_handoff_replay_receipt_fails_closed_if_transported_bytes_change(
    monkeypatch, tmp_path: Path
) -> None:
    manifest, extension_chain, evidence, _root_store, _roots, bundle, path = _export(
        monkeypatch, tmp_path
    )
    receipt = build_pilot_startup_evidence_handoff_replay_receipt(
        path, manifest, extension_chain, evidence
    )
    digest = bundle["artifact_digests"]["startup_receipts"][0]
    artifact = path / "artifacts" / "startup_receipts" / f"{digest}.json"
    artifact.write_bytes(b"{}\n")

    assert not verify_pilot_startup_evidence_handoff_replay_receipt(
        receipt, path, manifest, extension_chain, evidence
    )


def test_handoff_replay_receipt_rejects_wrong_expected_root(monkeypatch, tmp_path: Path) -> None:
    manifest, extension_chain, evidence, _root_store, _roots, _bundle, path = _export(
        monkeypatch, tmp_path
    )
    receipt = build_pilot_startup_evidence_handoff_replay_receipt(
        path, manifest, extension_chain, evidence
    )
    wrong_manifest = dict(manifest)
    wrong_manifest["root_manifest_sha256"] = "0" * 64

    assert not verify_pilot_startup_evidence_handoff_replay_receipt(
        receipt, path, wrong_manifest, extension_chain, evidence
    )
