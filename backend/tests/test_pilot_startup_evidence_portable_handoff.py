from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.pilot_startup_evidence_portable_handoff import (
    verify_pilot_startup_evidence_portable_handoff,
    verify_pilot_startup_evidence_portable_handoff_semantics,
    export_pilot_startup_evidence_portable_handoff,
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


def _canonical_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    ) + b"\n"


def _rebind_handoff_file_digest(path: Path, relative: str) -> None:
    handoff_path = path / "handoff-manifest.json"
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    handoff["files"][relative] = hashlib.sha256((path / relative).read_bytes()).hexdigest()
    unsigned = {key: value for key, value in handoff.items() if key != "handoff_manifest_sha256"}
    handoff["handoff_manifest_sha256"] = hashlib.sha256(
        _canonical_bytes(unsigned).rstrip(b"\n")
    ).hexdigest()
    handoff_path.write_bytes(_canonical_bytes(handoff))


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


def test_portable_handoff_semantic_replay_accepts_verified_transported_graph(
    monkeypatch, tmp_path: Path
) -> None:
    manifest, extension_chain, evidence, _root_store, _roots, _bundle, path = _export(
        monkeypatch, tmp_path
    )

    assert verify_pilot_startup_evidence_portable_handoff(path)
    assert verify_pilot_startup_evidence_portable_handoff_semantics(
        path, manifest, extension_chain, evidence
    )


def test_portable_handoff_semantic_replay_rejects_plain_byte_tamper(
    monkeypatch, tmp_path: Path
) -> None:
    manifest, extension_chain, evidence, _root_store, _roots, bundle, path = _export(
        monkeypatch, tmp_path
    )
    digest = bundle["artifact_digests"]["catalogs"][0]
    artifact = path / "artifacts" / "catalogs" / f"{digest}.json"
    artifact.write_bytes(b"{}\n")

    assert not verify_pilot_startup_evidence_portable_handoff(path)
    assert not verify_pilot_startup_evidence_portable_handoff_semantics(
        path, manifest, extension_chain, evidence
    )


def test_portable_handoff_semantic_replay_detects_semantic_tamper_even_if_byte_inventory_is_rebound(
    monkeypatch, tmp_path: Path
) -> None:
    manifest, extension_chain, evidence, _root_store, _roots, bundle, path = _export(
        monkeypatch, tmp_path
    )
    digest = bundle["artifact_digests"]["startup_receipts"][0]
    relative = f"artifacts/startup_receipts/{digest}.json"
    artifact = path / relative
    artifact.write_bytes(b"{}\n")
    _rebind_handoff_file_digest(path, relative)

    # The handoff-level checksum inventory can be made internally consistent with arbitrary replacement
    # bytes, but the transported semantic verifier must still fail closed on the evidence contract.
    assert verify_pilot_startup_evidence_portable_handoff(path)
    assert not verify_pilot_startup_evidence_portable_handoff_semantics(
        path, manifest, extension_chain, evidence
    )


def test_portable_handoff_semantic_replay_rejects_wrong_expected_graph(
    monkeypatch, tmp_path: Path
) -> None:
    manifest, extension_chain, evidence, _root_store, _roots, _bundle, path = _export(
        monkeypatch, tmp_path
    )
    wrong_manifest = dict(manifest)
    wrong_manifest["root_manifest_sha256"] = "0" * 64

    assert verify_pilot_startup_evidence_portable_handoff(path)
    assert not verify_pilot_startup_evidence_portable_handoff_semantics(
        path, wrong_manifest, extension_chain, evidence
    )
