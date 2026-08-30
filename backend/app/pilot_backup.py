from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .idempotency import IdempotencyJournal
from .storage import StateStore


BACKUP_SCHEMA = "morpheus-single-node-pilot-backup-v1"


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _sqlite_backup(source: sqlite3.Connection, destination: Path) -> None:
    connection = sqlite3.connect(str(destination))
    try:
        source.backup(connection)
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.commit()
    finally:
        connection.close()


def _sqlite_quick_check(path: Path) -> bool:
    connection = sqlite3.connect(str(path))
    try:
        row = connection.execute("PRAGMA quick_check").fetchone()
        return row is not None and row[0] == "ok"
    finally:
        connection.close()


def _ensure_new_directory_target(path: Path) -> None:
    if path.exists():
        raise ValueError(f"target already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)


def create_pilot_backup(
    *,
    store: StateStore,
    journal: IdempotencyJournal,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Create a consistent, content-hashed backup for the single-node pilot stores.

    The function serializes state/journal access while snapshotting. It refuses
    PENDING or AMBIGUOUS idempotency records because an operationally uncertain
    side effect must be resolved before calling the backup a recovery checkpoint.
    """

    if store.db_path == ":memory:" or journal.db_path == ":memory:":
        raise ValueError("pilot backup requires file-backed state and idempotency databases")

    destination = Path(output_dir).expanduser().resolve()
    _ensure_new_directory_target(destination)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.staging-", dir=destination.parent))
    try:
        state_dir = staging / "state"
        artifact_dir = staging / "artifacts"
        state_dir.mkdir(parents=True)
        artifact_dir.mkdir(parents=True)
        state_db_backup = state_dir / "morpheus.db"
        journal_db_backup = state_dir / "idempotency.db"

        # No normal MORPHEUS path holds both locks across operations. Acquiring
        # them together here creates a quiescent cross-store snapshot boundary.
        with ExitStack() as stack:
            stack.enter_context(journal._lock)
            stack.enter_context(store._lock)

            journal_status = journal.verify_integrity()
            if journal_status.get("valid") is not True or journal_status.get("durable") is not True:
                raise ValueError("idempotency journal is not a valid durable backup source")
            states = journal_status.get("states", {})
            if int(states.get("PENDING", 0)) != 0 or int(states.get("AMBIGUOUS_FAILURE", 0)) != 0:
                raise ValueError("pilot backup requires zero PENDING and zero AMBIGUOUS_FAILURE idempotency records")

            ledger = store.verify_evidence_ledger()
            if ledger.get("valid") is not True:
                raise ValueError("evidence ledger integrity must pass before backup")

            _sqlite_backup(store._connection, state_db_backup)
            _sqlite_backup(journal._connection, journal_db_backup)

            artifact_rows = store._connection.execute(
                "SELECT sha256, relative_path, size_bytes FROM artifacts ORDER BY sha256"
            ).fetchall()
            artifact_inventory: list[dict[str, Any]] = []
            for row in artifact_rows:
                sha256 = str(row["sha256"])
                relative = Path(str(row["relative_path"]))
                source = (store.artifact_root / relative).resolve()
                if store.artifact_root not in source.parents or not source.is_file():
                    raise ValueError(f"referenced artifact is missing or escaped the content-addressed root: {sha256}")
                if _file_sha256(source) != sha256:
                    raise ValueError(f"referenced artifact checksum mismatch: {sha256}")
                target = (artifact_dir / relative).resolve()
                if artifact_dir not in target.parents:
                    raise ValueError("artifact backup path escaped backup root")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                copied_sha = _file_sha256(target)
                if copied_sha != sha256:
                    raise RuntimeError(f"artifact copy checksum mismatch: {sha256}")
                artifact_inventory.append(
                    {
                        "sha256": sha256,
                        "relative_path": relative.as_posix(),
                        "size_bytes": int(row["size_bytes"]),
                    }
                )

            state_summary = store.summary()

        if not _sqlite_quick_check(state_db_backup) or not _sqlite_quick_check(journal_db_backup):
            raise RuntimeError("SQLite backup integrity check failed")

        core = {
            "schema": BACKUP_SCHEMA,
            "created_at": datetime.now(UTC).isoformat(),
            "state_database": {
                "path": "state/morpheus.db",
                "sha256": _file_sha256(state_db_backup),
                "size_bytes": state_db_backup.stat().st_size,
            },
            "idempotency_database": {
                "path": "state/idempotency.db",
                "sha256": _file_sha256(journal_db_backup),
                "size_bytes": journal_db_backup.stat().st_size,
            },
            "artifact_inventory": artifact_inventory,
            "artifact_count": len(artifact_inventory),
            "state_summary": state_summary,
            "evidence_ledger": {
                "entries": int(ledger.get("entries", 0)),
                "head_hash": ledger.get("head_hash"),
                "evidence_state": ledger.get("evidence_state"),
            },
            "idempotency_states": dict(journal_status.get("states", {})),
            "evidence_state": "CONTENT_HASHED_QUIESCENT_SINGLE_NODE_PILOT_BACKUP",
            "truth_boundaries": [
                "The backup is a recovery checkpoint for the declared single-node SQLite/local-CAS pilot, not continuous replication or high availability.",
                "Backup creation serializes MORPHEUS state/journal access and requires zero pending/ambiguous idempotency records; external processes writing the same files are outside this guarantee.",
                "Restore verification proves byte and SQLite integrity plus MORPHEUS ledger/journal checks; it does not prove application-level continuity under an untested deployment topology.",
            ],
        }
        manifest = {**core, "backup_sha256": _canonical_sha256(core)}
        manifest_path = staging / "backup-manifest.json"
        manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")

        os.replace(staging, destination)
        return manifest
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def verify_pilot_backup(backup_dir: str | Path) -> dict[str, Any]:
    root = Path(backup_dir).expanduser().resolve()
    manifest_path = root / "backup-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("backup manifest is missing")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != BACKUP_SCHEMA:
        raise ValueError("unexpected pilot backup schema")
    backup_sha = payload.get("backup_sha256")
    core = {key: value for key, value in payload.items() if key != "backup_sha256"}
    if backup_sha != _canonical_sha256(core):
        raise ValueError("pilot backup manifest hash mismatch")

    for field in ("state_database", "idempotency_database"):
        item = payload.get(field)
        if not isinstance(item, dict):
            raise ValueError(f"backup manifest lacks {field}")
        path = (root / str(item.get("path", ""))).resolve()
        if root not in path.parents or not path.is_file():
            raise ValueError(f"backup {field} path is missing or escaped backup root")
        if _file_sha256(path) != item.get("sha256") or path.stat().st_size != item.get("size_bytes"):
            raise ValueError(f"backup {field} byte identity mismatch")
        if not _sqlite_quick_check(path):
            raise ValueError(f"backup {field} SQLite integrity check failed")

    inventory = payload.get("artifact_inventory")
    if not isinstance(inventory, list) or payload.get("artifact_count") != len(inventory):
        raise ValueError("backup artifact inventory is inconsistent")
    seen: set[str] = set()
    for item in inventory:
        if not isinstance(item, dict):
            raise ValueError("backup artifact inventory entries must be objects")
        sha256 = str(item.get("sha256", ""))
        if sha256 in seen:
            raise ValueError("backup artifact inventory contains duplicate hashes")
        seen.add(sha256)
        path = (root / "artifacts" / str(item.get("relative_path", ""))).resolve()
        artifact_root = (root / "artifacts").resolve()
        if artifact_root not in path.parents or not path.is_file():
            raise ValueError(f"backup artifact is missing or escaped artifact root: {sha256}")
        if _file_sha256(path) != sha256 or path.stat().st_size != item.get("size_bytes"):
            raise ValueError(f"backup artifact byte identity mismatch: {sha256}")

    return {
        "valid": True,
        "schema": BACKUP_SCHEMA,
        "backup_sha256": backup_sha,
        "artifact_count": len(inventory),
        "evidence_state": "PILOT_BACKUP_BYTE_AND_SQLITE_INTEGRITY_VERIFIED",
        "truth_boundary": "This verification checks backup bytes and SQLite structure; MORPHEUS semantic restore checks occur only after restoring into an isolated target.",
    }


def restore_pilot_backup(
    backup_dir: str | Path,
    *,
    target_state_dir: str | Path,
) -> dict[str, Any]:
    """Restore into a new isolated directory and verify MORPHEUS semantic stores.

    Existing targets are never overwritten. The caller must explicitly point a
    future MORPHEUS process at the returned DB/artifact paths after inspection.
    """

    verification = verify_pilot_backup(backup_dir)
    source_root = Path(backup_dir).expanduser().resolve()
    target = Path(target_state_dir).expanduser().resolve()
    _ensure_new_directory_target(target)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.restore-", dir=target.parent))
    restored_store: StateStore | None = None
    restored_journal: IdempotencyJournal | None = None
    try:
        shutil.copy2(source_root / "state" / "morpheus.db", staging / "morpheus.db")
        shutil.copy2(source_root / "state" / "idempotency.db", staging / "idempotency.db")
        shutil.copytree(source_root / "artifacts", staging / "artifacts")

        restored_store = StateStore(db_path=staging / "morpheus.db", artifact_root=staging / "artifacts")
        restored_journal = IdempotencyJournal(staging / "idempotency.db")
        ledger = restored_store.verify_evidence_ledger()
        journal_status = restored_journal.verify_integrity()
        if ledger.get("valid") is not True:
            raise ValueError("restored MORPHEUS evidence ledger failed integrity verification")
        if journal_status.get("valid") is not True:
            raise ValueError("restored idempotency journal failed integrity verification")

        manifest = json.loads((source_root / "backup-manifest.json").read_text(encoding="utf-8"))
        for item in manifest.get("artifact_inventory", []):
            sha256 = str(item["sha256"])
            restored = restored_store.read_artifact(sha256)
            if restored is None:
                raise ValueError(f"restored state cannot resolve referenced artifact: {sha256}")

        # Close SQLite/WAL handles before directory promotion. This matters on
        # Windows, where an open database file cannot be atomically renamed.
        with restored_store._lock:
            restored_store._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            restored_store._connection.close()
        restored_store = None
        with restored_journal._lock:
            restored_journal._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            restored_journal._connection.close()
        restored_journal = None

        os.replace(staging, target)
        return {
            "schema": "morpheus-single-node-pilot-restore-v1",
            "restored": True,
            "backup_sha256": verification["backup_sha256"],
            "state_database": str(target / "morpheus.db"),
            "idempotency_database": str(target / "idempotency.db"),
            "artifact_directory": str(target / "artifacts"),
            "evidence_ledger_entries": int(ledger.get("entries", 0)),
            "artifact_count": int(verification["artifact_count"]),
            "evidence_state": "ISOLATED_PILOT_BACKUP_RESTORE_VERIFIED",
            "truth_boundary": "The restore is isolated and verified; it has not automatically replaced the active MORPHEUS state or proven failover/HA behavior.",
        }
    except Exception:
        if restored_store is not None:
            try:
                with restored_store._lock:
                    restored_store._connection.close()
            except Exception:
                pass
        if restored_journal is not None:
            try:
                with restored_journal._lock:
                    restored_journal._connection.close()
            except Exception:
                pass
        shutil.rmtree(staging, ignore_errors=True)
        raise
