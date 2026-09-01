from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.pilot_startup_evidence_catalog import build_pilot_startup_evidence_catalog
from app.pilot_startup_evidence_catalog_store import PilotStartupEvidenceCatalogStore
from app.pilot_startup_evidence_checkpoint_chain import (
    build_pilot_startup_evidence_checkpoint_chain,
    verify_pilot_startup_evidence_checkpoint_chain,
    verify_pilot_startup_evidence_checkpoint_chain_against_store,
)


def _catalog(tmp_path: Path, name: str, receipt_digest: str) -> dict:
    root = tmp_path / name
    root.mkdir()
    payload = {"startup_evidence_sha256": receipt_digest}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    (root / f"{receipt_digest}.json").write_bytes(canonical)
    return build_pilot_startup_evidence_catalog(root)


def test_checkpoint_chain_is_deterministic_order_sensitive_and_verified(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.pilot_startup_evidence_store.verify_pilot_startup_evidence", lambda payload: True)
    first = _catalog(tmp_path, "evidence-a", "a" * 64)
    second = _catalog(tmp_path, "evidence-b", "b" * 64)
    digests = [first["catalog_sha256"], second["catalog_sha256"]]
    left = build_pilot_startup_evidence_checkpoint_chain(digests)
    right = build_pilot_startup_evidence_checkpoint_chain(digests)
    reversed_chain = build_pilot_startup_evidence_checkpoint_chain(list(reversed(digests)))

    assert left == right
    assert verify_pilot_startup_evidence_checkpoint_chain(left)
    assert left["checkpoint_count"] == 2
    assert left["chain_sha256"] != reversed_chain["chain_sha256"]
    assert left["production_deployment_authorized"] is False
    assert "not a digital signature" in left["truth_boundary"]
    assert "trusted timestamp" in left["truth_boundary"]


def test_checkpoint_chain_rejects_replay_and_malformed_digests() -> None:
    digest = "a" * 64
    with pytest.raises(ValueError, match="replay"):
        build_pilot_startup_evidence_checkpoint_chain([digest, digest])
    for value in ("", "a" * 63, "A" * 64, "g" * 64):
        with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
            build_pilot_startup_evidence_checkpoint_chain([value])
    with pytest.raises(ValueError, match="at least one"):
        build_pilot_startup_evidence_checkpoint_chain([])


def test_checkpoint_chain_rejects_tampering_boolean_alias_and_authority_widening() -> None:
    chain = build_pilot_startup_evidence_checkpoint_chain(["a" * 64, "b" * 64])

    tampered = dict(chain)
    tampered["checkpoint_count"] = True
    assert not verify_pilot_startup_evidence_checkpoint_chain(tampered)

    tampered = dict(chain)
    tampered["catalog_sha256_chain"] = ["b" * 64, "a" * 64]
    assert not verify_pilot_startup_evidence_checkpoint_chain(tampered)

    tampered = dict(chain)
    tampered["production_deployment_authorized"] = True
    assert not verify_pilot_startup_evidence_checkpoint_chain(tampered)

    tampered = dict(chain)
    tampered["unexpected"] = "field"
    assert not verify_pilot_startup_evidence_checkpoint_chain(tampered)


def test_checkpoint_chain_store_binding_requires_every_verified_catalog(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.pilot_startup_evidence_store.verify_pilot_startup_evidence", lambda payload: True)
    checkpoint_root = tmp_path / "checkpoints"
    catalog_store = PilotStartupEvidenceCatalogStore(checkpoint_root)
    first = _catalog(tmp_path, "evidence-a", "a" * 64)
    second = _catalog(tmp_path, "evidence-b", "b" * 64)
    first_path = catalog_store.persist(first)
    second_path = catalog_store.persist(second)
    chain = build_pilot_startup_evidence_checkpoint_chain(
        [first["catalog_sha256"], second["catalog_sha256"]]
    )

    assert verify_pilot_startup_evidence_checkpoint_chain_against_store(chain, checkpoint_root)

    second_path.unlink()
    assert not verify_pilot_startup_evidence_checkpoint_chain_against_store(chain, checkpoint_root)

    catalog_store.persist(second)
    first_path.write_bytes(b"{}\n")
    assert not verify_pilot_startup_evidence_checkpoint_chain_against_store(chain, checkpoint_root)
