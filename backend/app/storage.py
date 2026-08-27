from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from .models import SynthesisResult, WorkloadSpec
from .parser import canonical_dict


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class StateStore:
    """SQLite metadata + content-addressed small artifact store.

    The store is intentionally boring: no ORM, no implicit migrations, no
    arbitrary path inputs. This keeps the provenance boundary inspectable and
    lets the MVP run locally without external infrastructure. Production can
    replace this adapter with PostgreSQL/object storage behind the same methods.
    """

    def __init__(self, db_path: str | Path | None = None, artifact_root: str | Path | None = None) -> None:
        default_state_dir = Path(os.environ.get("MORPHEUS_STATE_DIR", Path.home() / ".morpheus"))
        configured_db = os.environ.get("MORPHEUS_DB_PATH")
        if db_path is None:
            db_path = configured_db or (default_state_dir / "morpheus.db")

        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

        root = Path(artifact_root or os.environ.get("MORPHEUS_ARTIFACT_DIR", default_state_dir / "artifacts"))
        self.artifact_root = root.expanduser().resolve()
        self.artifact_root.mkdir(parents=True, exist_ok=True)

        self._lock = RLock()
        self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        if self.db_path != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA synchronous = NORMAL")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workloads (
                    spec_hash TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    spec_text TEXT NOT NULL,
                    canonical_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS synthesis_runs (
                    run_id TEXT PRIMARY KEY,
                    spec_hash TEXT NOT NULL REFERENCES workloads(spec_hash),
                    strategy TEXT NOT NULL,
                    evidence_state TEXT NOT NULL,
                    winner_candidate_id TEXT,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_synthesis_runs_created
                    ON synthesis_runs(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_synthesis_runs_spec_hash
                    ON synthesis_runs(spec_hash, created_at DESC);

                CREATE TABLE IF NOT EXISTS artifacts (
                    sha256 TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    candidate_id TEXT,
                    spec_hash TEXT,
                    file_name TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    evidence_state TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    message TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_audit_events_timestamp
                    ON audit_events(event_id DESC);
                """
            )

    def save_synthesis(self, spec: WorkloadSpec, spec_text: str, result: SynthesisResult) -> str:
        run_id = str(uuid.uuid4())
        now = _utc_now()
        canonical_json = json.dumps(canonical_dict(spec), sort_keys=True, separators=(",", ":"))
        result_json = json.dumps(result.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        strategy = result.search_summary.strategy.value if result.search_summary else "unknown"
        winner_id = result.winner.id if result.winner else None

        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO workloads(spec_hash, name, spec_text, canonical_json, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(spec_hash) DO UPDATE SET
                    name=excluded.name,
                    spec_text=excluded.spec_text,
                    canonical_json=excluded.canonical_json,
                    updated_at=excluded.updated_at
                """,
                (result.spec_hash, spec.name, spec_text, canonical_json, now, now),
            )
            self._connection.execute(
                """
                INSERT INTO synthesis_runs(
                    run_id, spec_hash, strategy, evidence_state, winner_candidate_id, result_json, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, result.spec_hash, strategy, result.evidence_state, winner_id, result_json, now),
            )
        return run_id

    def list_runs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        limit = min(max(limit, 1), 500)
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT r.run_id, r.spec_hash, w.name, r.strategy, r.evidence_state,
                       r.winner_candidate_id, r.created_at
                FROM synthesis_runs r
                JOIN workloads w ON w.spec_hash = r.spec_hash
                ORDER BY r.created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT r.*, w.name, w.spec_text, w.canonical_json
                FROM synthesis_runs r
                JOIN workloads w ON w.spec_hash = r.spec_hash
                WHERE r.run_id = ?
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        payload = dict(row)
        payload["result"] = json.loads(payload.pop("result_json"))
        payload["canonical_spec"] = json.loads(payload.pop("canonical_json"))
        return payload

    def list_workloads(self, *, limit: int = 100) -> list[dict[str, Any]]:
        limit = min(max(limit, 1), 500)
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT w.spec_hash, w.name, w.created_at, w.updated_at,
                       COUNT(r.run_id) AS run_count,
                       MAX(r.created_at) AS last_run_at
                FROM workloads w
                LEFT JOIN synthesis_runs r ON r.spec_hash = w.spec_hash
                GROUP BY w.spec_hash, w.name, w.created_at, w.updated_at
                ORDER BY COALESCE(MAX(r.created_at), w.updated_at) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def store_artifact(
        self,
        *,
        content: str,
        kind: str,
        file_name: str,
        evidence_state: str,
        candidate_id: str | None = None,
        spec_hash: str | None = None,
    ) -> dict[str, Any]:
        raw = content.encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        suffix = Path(file_name).suffix or ".txt"
        relative = Path(digest[:2]) / f"{digest}{suffix}"
        destination = (self.artifact_root / relative).resolve()
        if self.artifact_root not in destination.parents:
            raise ValueError("artifact path escaped content-addressed root")
        destination.parent.mkdir(parents=True, exist_ok=True)

        if not destination.exists():
            temporary = destination.with_suffix(destination.suffix + f".{uuid.uuid4().hex}.tmp")
            temporary.write_bytes(raw)
            os.replace(temporary, destination)

        now = _utc_now()
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO artifacts(
                    sha256, kind, candidate_id, spec_hash, file_name, relative_path,
                    size_bytes, evidence_state, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sha256) DO NOTHING
                """,
                (
                    digest,
                    kind,
                    candidate_id,
                    spec_hash,
                    file_name,
                    relative.as_posix(),
                    len(raw),
                    evidence_state,
                    now,
                ),
            )
        return self.get_artifact_metadata(digest) or {}

    def get_artifact_metadata(self, sha256: str) -> dict[str, Any] | None:
        if not _SHA256_RE.fullmatch(sha256):
            return None
        with self._lock:
            row = self._connection.execute("SELECT * FROM artifacts WHERE sha256 = ?", (sha256,)).fetchone()
        return dict(row) if row else None

    def read_artifact(self, sha256: str) -> tuple[dict[str, Any], str] | None:
        metadata = self.get_artifact_metadata(sha256)
        if metadata is None:
            return None
        relative = Path(metadata["relative_path"])
        path = (self.artifact_root / relative).resolve()
        if self.artifact_root not in path.parents or not path.is_file():
            return None
        content = path.read_text(encoding="utf-8")
        if hashlib.sha256(content.encode("utf-8")).hexdigest() != sha256:
            raise RuntimeError("artifact checksum mismatch")
        return metadata, content

    def record_event(self, kind: str, message: str, payload: dict[str, Any]) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO audit_events(timestamp, kind, message, payload_json) VALUES(?, ?, ?, ?)",
                (_utc_now(), kind, message, json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)),
            )

    def recent_events(self, *, limit: int = 200) -> list[dict[str, Any]]:
        limit = min(max(limit, 1), 1000)
        with self._lock:
            rows = self._connection.execute(
                "SELECT timestamp, kind, message, payload_json FROM audit_events ORDER BY event_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "timestamp": row["timestamp"],
                "kind": row["kind"],
                "message": row["message"],
                "payload": json.loads(row["payload_json"]),
            }
            for row in rows
        ]

    def summary(self) -> dict[str, Any]:
        with self._lock:
            workload_count = self._connection.execute("SELECT COUNT(*) FROM workloads").fetchone()[0]
            run_count = self._connection.execute("SELECT COUNT(*) FROM synthesis_runs").fetchone()[0]
            artifact_count = self._connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
            event_count = self._connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        return {
            "workloads": workload_count,
            "synthesis_runs": run_count,
            "artifacts": artifact_count,
            "audit_events": event_count,
            "database": "sqlite",
            "artifact_store": "content_addressed_filesystem",
        }


STORE = StateStore()
