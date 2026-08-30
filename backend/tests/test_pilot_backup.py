from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.idempotency import IdempotencyJournal, request_sha256
from app.pilot_backup import create_pilot_backup, restore_pilot_backup, verify_pilot_backup
from app.storage import StateStore


def _stores(tmp_path: Path) -> tuple[StateStore, IdempotencyJournal]:
    return (
        StateStore(db_path=tmp_path / "source" / "morpheus.db", artifact_root=tmp_path / "source" / "artifacts"),
        IdempotencyJournal(tmp_path / "source" / "idempotency.db"),
    )


def _completed_journal_entry(journal: IdempotencyJournal) -> None:
    digest = request_sha256({"fixture": True})
    claim = journal.claim(operation="backup-fixture", key="pilot-backup-fixture-key", request_digest=digest)
    journal.complete(
        operation="backup-fixture",
        key_sha256=claim.key_sha256,
        request_digest=digest,
        status_code=200,
        response_payload={"ok": True},
    )


def test_backup_verify_and_isolated_restore_round_trip(tmp_path: Path) -> None:
    store, journal = _stores(tmp_path)
    artifact = store.store_artifact(
        content="pilot artifact body",
        kind="pilot_fixture",
        file_name="fixture.txt",
        evidence_state="TEST_FIXTURE",
    )
    store.append_evidence(kind="pilot-test", subject="backup", payload={"artifact_sha256": artifact["sha256"]})
    _completed_journal_entry(journal)

    backup_dir = tmp_path / "backup"
    manifest = create_pilot_backup(store=store, journal=journal, output_dir=backup_dir)
    assert manifest["schema"] == "morpheus-single-node-pilot-backup-v1"
    assert manifest["artifact_count"] == 1
    assert manifest["idempotency_states"]["COMPLETED"] == 1
    assert manifest["idempotency_states"]["PENDING"] == 0
    assert len(manifest["backup_sha256"]) == 64

    verified = verify_pilot_backup(backup_dir)
    assert verified["valid"] is True
    assert verified["backup_sha256"] == manifest["backup_sha256"]

    restore_dir = tmp_path / "restore"
    restored = restore_pilot_backup(backup_dir, target_state_dir=restore_dir)
    assert restored["restored"] is True
    assert restored["backup_sha256"] == manifest["backup_sha256"]
    assert restored["artifact_count"] == 1

    restored_store = StateStore(db_path=restore_dir / "morpheus.db", artifact_root=restore_dir / "artifacts")
    restored_journal = IdempotencyJournal(restore_dir / "idempotency.db")
    assert restored_store.verify_evidence_ledger()["valid"] is True
    assert restored_journal.verify_integrity()["states"]["COMPLETED"] == 1
    restored_artifact = restored_store.read_artifact(str(artifact["sha256"]))
    assert restored_artifact is not None
    assert restored_artifact[1] == "pilot artifact body"


def test_backup_refuses_pending_or_ambiguous_idempotency_state(tmp_path: Path) -> None:
    store, journal = _stores(tmp_path)
    digest = request_sha256({"fixture": "pending"})
    journal.claim(operation="backup-fixture", key="pilot-backup-pending-key", request_digest=digest)
    with pytest.raises(ValueError, match="zero PENDING"):
        create_pilot_backup(store=store, journal=journal, output_dir=tmp_path / "backup-pending")

    store2 = StateStore(db_path=tmp_path / "source2" / "morpheus.db", artifact_root=tmp_path / "source2" / "artifacts")
    journal2 = IdempotencyJournal(tmp_path / "source2" / "idempotency.db")
    claim = journal2.claim(operation="backup-fixture", key="pilot-backup-ambiguous-key", request_digest=digest)
    journal2.mark_ambiguous_failure(
        operation="backup-fixture",
        key_sha256=claim.key_sha256,
        request_digest=digest,
    )
    with pytest.raises(ValueError, match="AMBIGUOUS_FAILURE"):
        create_pilot_backup(store=store2, journal=journal2, output_dir=tmp_path / "backup-ambiguous")


def test_backup_verifier_rejects_artifact_tampering(tmp_path: Path) -> None:
    store, journal = _stores(tmp_path)
    artifact = store.store_artifact(
        content="immutable",
        kind="pilot_fixture",
        file_name="fixture.txt",
        evidence_state="TEST_FIXTURE",
    )
    backup_dir = tmp_path / "backup"
    create_pilot_backup(store=store, journal=journal, output_dir=backup_dir)

    manifest = json.loads((backup_dir / "backup-manifest.json").read_text(encoding="utf-8"))
    item = next(entry for entry in manifest["artifact_inventory"] if entry["sha256"] == artifact["sha256"])
    path = backup_dir / "artifacts" / item["relative_path"]
    path.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact byte identity mismatch"):
        verify_pilot_backup(backup_dir)


def test_restore_never_overwrites_existing_target(tmp_path: Path) -> None:
    store, journal = _stores(tmp_path)
    backup_dir = tmp_path / "backup"
    create_pilot_backup(store=store, journal=journal, output_dir=backup_dir)
    existing = tmp_path / "existing"
    existing.mkdir()
    (existing / "keep.txt").write_text("do not overwrite", encoding="utf-8")

    with pytest.raises(ValueError, match="target already exists"):
        restore_pilot_backup(backup_dir, target_state_dir=existing)
    assert (existing / "keep.txt").read_text(encoding="utf-8") == "do not overwrite"
