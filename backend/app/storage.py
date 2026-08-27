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

from .decision_certificate import build_decision_certificate
from .models import CalibrationProfile, SynthesisResult, WorkloadSpec
from .parser import canonical_dict


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ZERO_HASH = "0" * 64


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


class StateStore:
    """SQLite metadata + content-addressed artifact and evidence store.

    The local store deliberately keeps the implementation inspectable: no ORM,
    no arbitrary paths and no hidden network dependency. Calibration profiles,
    run/artifact links, immutable decision certificates, and the append-only
    hash-chained evidence ledger are durable so provenance survives restarts.
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

                CREATE TABLE IF NOT EXISTS run_artifacts (
                    run_id TEXT NOT NULL REFERENCES synthesis_runs(run_id) ON DELETE CASCADE,
                    sha256 TEXT NOT NULL REFERENCES artifacts(sha256),
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(run_id, sha256, role)
                );

                CREATE INDEX IF NOT EXISTS idx_run_artifacts_role
                    ON run_artifacts(run_id, role, created_at DESC);

                CREATE TABLE IF NOT EXISTS calibration_profiles (
                    profile_id TEXT PRIMARY KEY,
                    profile_json TEXT NOT NULL,
                    protocol TEXT NOT NULL,
                    evidence_state TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 0 CHECK(is_active IN (0, 1)),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_calibration_single_active
                    ON calibration_profiles(is_active) WHERE is_active = 1;

                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    message TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_audit_events_timestamp
                    ON audit_events(event_id DESC);

                CREATE TABLE IF NOT EXISTS evidence_ledger (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    entry_hash TEXT NOT NULL UNIQUE
                );

                CREATE INDEX IF NOT EXISTS idx_evidence_ledger_sequence
                    ON evidence_ledger(sequence DESC);
                """
            )

    def save_synthesis(self, spec: WorkloadSpec, spec_text: str, result: SynthesisResult) -> str:
        run_id = str(uuid.uuid4())
        now = _utc_now()
        canonical_json = _canonical_json(canonical_dict(spec))
        result_json = _canonical_json(result.model_dump(mode="json"))
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

        certificate = build_decision_certificate(run_id=run_id, spec=spec, result=result)
        metadata = self.store_artifact(
            content=json.dumps(certificate, sort_keys=True, indent=2),
            kind="synthesis_decision_certificate",
            file_name=f"decision-{run_id}.json",
            evidence_state="SYNTHESIS_DECISION_CERTIFICATE",
            candidate_id=winner_id,
            spec_hash=result.spec_hash,
        )
        certificate_sha = str(metadata.get("sha256", ""))
        if certificate_sha:
            self.link_run_artifact(run_id, certificate_sha, role="decision_certificate")
            self.append_evidence(
                kind="synthesis_decision_certificate",
                subject=run_id,
                payload={
                    "run_id": run_id,
                    "spec_hash": result.spec_hash,
                    "candidate_id": winner_id,
                    "certificate_sha256": certificate_sha,
                    "evidence_state": result.evidence_state,
                },
            )
        return run_id

    def list_runs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        limit = min(max(limit, 1), 500)
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT r.run_id, r.spec_hash, w.name, r.strategy, r.evidence_state,
                       r.winner_candidate_id, r.created_at,
                       COUNT(ra.sha256) AS linked_artifact_count
                FROM synthesis_runs r
                JOIN workloads w ON w.spec_hash = r.spec_hash
                LEFT JOIN run_artifacts ra ON ra.run_id = r.run_id
                GROUP BY r.run_id, r.spec_hash, w.name, r.strategy, r.evidence_state,
                         r.winner_candidate_id, r.created_at
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
        payload["artifacts"] = self.list_run_artifacts(run_id)
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

    def link_run_artifact(self, run_id: str, sha256: str, *, role: str) -> dict[str, Any]:
        if not role or len(role) > 128:
            raise ValueError("artifact role must contain 1-128 characters")
        if self.get_run_base(run_id) is None:
            raise KeyError(f"unknown synthesis run: {run_id}")
        if self.get_artifact_metadata(sha256) is None:
            raise KeyError(f"unknown artifact: {sha256}")
        now = _utc_now()
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO run_artifacts(run_id, sha256, role, created_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(run_id, sha256, role) DO NOTHING
                """,
                (run_id, sha256, role, now),
            )
        matches = [item for item in self.list_run_artifacts(run_id) if item["sha256"] == sha256 and item["role"] == role]
        return matches[0] if matches else {}

    def get_run_base(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT run_id, spec_hash, evidence_state, winner_candidate_id, created_at FROM synthesis_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_run_artifacts(self, run_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT ra.run_id, ra.role, ra.created_at AS linked_at,
                       a.sha256, a.kind, a.candidate_id, a.spec_hash, a.file_name,
                       a.size_bytes, a.evidence_state, a.created_at
                FROM run_artifacts ra
                JOIN artifacts a ON a.sha256 = ra.sha256
                WHERE ra.run_id = ?
                ORDER BY ra.created_at ASC, ra.role ASC
                """,
                (run_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def find_run_artifact(self, run_id: str, role: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT a.*, ra.role, ra.created_at AS linked_at
                FROM run_artifacts ra
                JOIN artifacts a ON a.sha256 = ra.sha256
                WHERE ra.run_id = ? AND ra.role = ?
                ORDER BY ra.created_at DESC LIMIT 1
                """,
                (run_id, role),
            ).fetchone()
        return dict(row) if row else None

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

    def save_calibration_profile(self, profile: CalibrationProfile, *, activate: bool = False) -> None:
        now = _utc_now()
        profile_json = _canonical_json(profile.model_dump(mode="json"))
        with self._lock, self._connection:
            if activate:
                self._connection.execute("UPDATE calibration_profiles SET is_active = 0 WHERE is_active = 1")
            self._connection.execute(
                """
                INSERT INTO calibration_profiles(
                    profile_id, profile_json, protocol, evidence_state, is_active, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(profile_id) DO UPDATE SET
                    profile_json=excluded.profile_json,
                    protocol=excluded.protocol,
                    evidence_state=excluded.evidence_state,
                    is_active=CASE WHEN excluded.is_active = 1 THEN 1 ELSE calibration_profiles.is_active END,
                    updated_at=excluded.updated_at
                """,
                (
                    profile.id,
                    profile_json,
                    profile.protocol,
                    profile.evidence_state,
                    1 if activate else 0,
                    now,
                    now,
                ),
            )

    def set_active_calibration(self, profile_id: str | None) -> None:
        with self._lock, self._connection:
            self._connection.execute("UPDATE calibration_profiles SET is_active = 0 WHERE is_active = 1")
            if profile_id is None:
                return
            cursor = self._connection.execute(
                "UPDATE calibration_profiles SET is_active = 1, updated_at = ? WHERE profile_id = ?",
                (_utc_now(), profile_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"unknown persisted calibration profile: {profile_id}")

    def load_calibration_profiles(self) -> tuple[list[CalibrationProfile], str | None]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT profile_json, profile_id, is_active FROM calibration_profiles ORDER BY profile_id"
            ).fetchall()
        profiles: list[CalibrationProfile] = []
        active: str | None = None
        for row in rows:
            profiles.append(CalibrationProfile.model_validate(json.loads(row["profile_json"])))
            if row["is_active"]:
                active = row["profile_id"]
        return profiles, active

    def record_event(self, kind: str, message: str, payload: dict[str, Any]) -> None:
        timestamp = _utc_now()
        payload_json = _canonical_json(payload)
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO audit_events(timestamp, kind, message, payload_json) VALUES(?, ?, ?, ?)",
                (timestamp, kind, message, payload_json),
            )
            self._append_evidence_locked(
                timestamp=timestamp,
                kind=f"audit:{kind}",
                subject=message,
                payload_json=payload_json,
            )

    def append_evidence(self, *, kind: str, subject: str, payload: dict[str, Any]) -> dict[str, Any]:
        timestamp = _utc_now()
        payload_json = _canonical_json(payload)
        with self._lock, self._connection:
            return self._append_evidence_locked(
                timestamp=timestamp,
                kind=kind,
                subject=subject,
                payload_json=payload_json,
            )

    def _append_evidence_locked(self, *, timestamp: str, kind: str, subject: str, payload_json: str) -> dict[str, Any]:
        previous_row = self._connection.execute(
            "SELECT entry_hash FROM evidence_ledger ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous_hash = previous_row["entry_hash"] if previous_row else _ZERO_HASH
        canonical_record = "\n".join([previous_hash, timestamp, kind, subject, payload_json])
        entry_hash = hashlib.sha256(canonical_record.encode("utf-8")).hexdigest()
        cursor = self._connection.execute(
            """
            INSERT INTO evidence_ledger(timestamp, kind, subject, payload_json, previous_hash, entry_hash)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (timestamp, kind, subject, payload_json, previous_hash, entry_hash),
        )
        return {
            "sequence": cursor.lastrowid,
            "timestamp": timestamp,
            "kind": kind,
            "subject": subject,
            "payload": json.loads(payload_json),
            "previous_hash": previous_hash,
            "entry_hash": entry_hash,
        }

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

    def recent_evidence(self, *, limit: int = 200) -> list[dict[str, Any]]:
        limit = min(max(limit, 1), 1000)
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT sequence, timestamp, kind, subject, payload_json, previous_hash, entry_hash
                FROM evidence_ledger ORDER BY sequence DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "sequence": row["sequence"],
                "timestamp": row["timestamp"],
                "kind": row["kind"],
                "subject": row["subject"],
                "payload": json.loads(row["payload_json"]),
                "previous_hash": row["previous_hash"],
                "entry_hash": row["entry_hash"],
            }
            for row in rows
        ]

    def verify_evidence_ledger(self) -> dict[str, Any]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT sequence, timestamp, kind, subject, payload_json, previous_hash, entry_hash
                FROM evidence_ledger ORDER BY sequence ASC
                """
            ).fetchall()
        expected_previous = _ZERO_HASH
        for row in rows:
            canonical_record = "\n".join(
                [expected_previous, row["timestamp"], row["kind"], row["subject"], row["payload_json"]]
            )
            expected_hash = hashlib.sha256(canonical_record.encode("utf-8")).hexdigest()
            if row["previous_hash"] != expected_previous or row["entry_hash"] != expected_hash:
                return {
                    "valid": False,
                    "entries": len(rows),
                    "failed_sequence": row["sequence"],
                    "expected_previous_hash": expected_previous,
                    "stored_previous_hash": row["previous_hash"],
                    "expected_entry_hash": expected_hash,
                    "stored_entry_hash": row["entry_hash"],
                    "evidence_state": "EVIDENCE_LEDGER_INTEGRITY_FAILURE",
                }
            expected_previous = row["entry_hash"]
        return {
            "valid": True,
            "entries": len(rows),
            "head_hash": expected_previous if rows else _ZERO_HASH,
            "evidence_state": "EVIDENCE_LEDGER_HASH_CHAIN_VERIFIED",
        }

    def summary(self) -> dict[str, Any]:
        with self._lock:
            workload_count = self._connection.execute("SELECT COUNT(*) FROM workloads").fetchone()[0]
            run_count = self._connection.execute("SELECT COUNT(*) FROM synthesis_runs").fetchone()[0]
            artifact_count = self._connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
            linked_artifact_count = self._connection.execute("SELECT COUNT(*) FROM run_artifacts").fetchone()[0]
            event_count = self._connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
            calibration_count = self._connection.execute("SELECT COUNT(*) FROM calibration_profiles").fetchone()[0]
            evidence_count = self._connection.execute("SELECT COUNT(*) FROM evidence_ledger").fetchone()[0]
            active_row = self._connection.execute(
                "SELECT profile_id FROM calibration_profiles WHERE is_active = 1 LIMIT 1"
            ).fetchone()
        return {
            "workloads": workload_count,
            "synthesis_runs": run_count,
            "artifacts": artifact_count,
            "linked_run_artifacts": linked_artifact_count,
            "audit_events": event_count,
            "calibration_profiles": calibration_count,
            "active_calibration_profile": active_row["profile_id"] if active_row else None,
            "evidence_entries": evidence_count,
            "database": "sqlite",
            "artifact_store": "content_addressed_filesystem",
        }


STORE = StateStore()
