from __future__ import annotations

from pathlib import Path

import pytest

from app.pilot_startup_evidence_catalog import build_pilot_startup_evidence_catalog
from app.pilot_startup_evidence_catalog_store import PilotStartupEvidenceCatalogStore
from app.pilot_startup_evidence_checkpoint_chain import build_pilot_startup_evidence_checkpoint_chain
from app.pilot_startup_evidence_checkpoint_chain_store import PilotStartupEvidenceCheckpointChainStore


def _catalog(root: Path) -> dict:
    return build_pilot_startup_evidence_catalog(root)


def test_chain_store_persists_loads_and_is_idempotent(tmp_path: Path) -> None:
    chain = build_pilot_startup_evidence_checkpoint_chain(["a" * 64, "b" * 64])
    store = PilotStartupEvidenceCheckpointChainStore(tmp_path / "chains")

    first = store.persist(chain)
    second = store.persist(chain)

    assert first == second
    assert first.name == f"{chain['chain_sha256']}.json"
    assert store.load(chain["chain_sha256"]) == chain


def test_chain_store_rejects_invalid_authority_and_boolean_alias(tmp_path: Path) -> None:
    chain = build_pilot_startup_evidence_checkpoint_chain(["a" * 64])
    store = PilotStartupEvidenceCheckpointChainStore(tmp_path / "chains")

    tampered = dict(chain)
    tampered["production_deployment_authorized"] = True
    with pytest.raises(ValueError, match="failed verification"):
        store.persist(tampered)

    tampered = dict(chain)
    tampered["checkpoint_count"] = True
    with pytest.raises(ValueError, match="failed verification"):
        store.persist(tampered)


def test_chain_store_detects_collision_tampering_and_noncanonical_json(tmp_path: Path) -> None:
    chain = build_pilot_startup_evidence_checkpoint_chain(["a" * 64])
    store = PilotStartupEvidenceCheckpointChainStore(tmp_path / "chains")
    path = store.persist(chain)

    path.write_bytes(b"{}\n")
    with pytest.raises(ValueError, match="collision|tampering"):
        store.persist(chain)
    with pytest.raises(ValueError, match="filename does not match|failed verification"):
        store.load(chain["chain_sha256"])

    path.write_text(" {\n}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        store.load(chain["chain_sha256"])


def test_chain_store_rejects_malformed_and_path_traversal_digests(tmp_path: Path) -> None:
    store = PilotStartupEvidenceCheckpointChainStore(tmp_path / "chains")
    for value in ("", "a" * 63, "A" * 64, "g" * 64, "../" + "a" * 64):
        with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
            store.path_for(value)


def test_chain_store_binding_requires_all_catalog_checkpoints(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.pilot_startup_evidence_store.verify_pilot_startup_evidence", lambda payload: True)
    evidence_a = tmp_path / "evidence-a"
    evidence_b = tmp_path / "evidence-b"
    evidence_a.mkdir()
    evidence_b.mkdir()

    import json

    for root, digest in ((evidence_a, "a" * 64), (evidence_b, "b" * 64)):
        payload = {"startup_evidence_sha256": digest}
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        (root / f"{digest}.json").write_bytes(canonical)

    first = _catalog(evidence_a)
    second = _catalog(evidence_b)
    catalog_root = tmp_path / "catalogs"
    catalog_store = PilotStartupEvidenceCatalogStore(catalog_root)
    first_path = catalog_store.persist(first)
    catalog_store.persist(second)

    chain = build_pilot_startup_evidence_checkpoint_chain(
        [first["catalog_sha256"], second["catalog_sha256"]]
    )
    chain_store = PilotStartupEvidenceCheckpointChainStore(tmp_path / "chains")
    chain_store.persist(chain)

    assert chain_store.verify_against_catalog_store(chain["chain_sha256"], catalog_root)

    first_path.unlink()
    assert not chain_store.verify_against_catalog_store(chain["chain_sha256"], catalog_root)
