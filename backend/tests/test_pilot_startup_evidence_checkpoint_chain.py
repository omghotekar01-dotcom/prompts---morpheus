from __future__ import annotations

from pathlib import Path

import pytest

from app.pilot_startup_evidence_catalog import build_pilot_startup_evidence_catalog
from app.pilot_startup_evidence_catalog_store import PilotStartupEvidenceCatalogStore
from app.pilot_startup_evidence_checkpoint_chain import (
    build_pilot_startup_evidence_checkpoint_chain,
    verify_pilot_startup_evidence_checkpoint_chain,
    verify_pilot_startup_evidence_checkpoint_chain_against_store,
)


def _catalog(tmp_path: Path, name: str) -> dict:
    return build_pilot_startup_evidence_catalog(tmp_path / name)


def test_checkpoint_chain_is_deterministic_order_sensitive_and_verified(tmp_path: Path) -> None:
    first = _catalog(tmp_path, "evidence-a")
    second = _catalog(tmp_path, "evidence-b")
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


def test_checkpoint_chain_store_binding_requires_every_verified_catalog(tmp_path: Path) -> None:
    checkpoint_root = tmp_path / "checkpoints"
    catalog_store = PilotStartupEvidenceCatalogStore(checkpoint_root)
    first = _catalog(tmp_path, "evidence-a")
    second = _catalog(tmp_path, "evidence-b")
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
