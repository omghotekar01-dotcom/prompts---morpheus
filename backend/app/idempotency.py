from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any


_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_STATES = {"PENDING", "COMPLETED", "AMBIGUOUS_FAILURE"}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def request_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_idempotency_key(value: str) -> str:
    if not isinstance(value, str) or value != value.strip() or not _KEY_RE.fullmatch(value):
        raise ValueError("Idempotency-Key must be 8-128 canonical characters: letters, digits, '.', '_', ':', '-'")
    return value


@dataclass(frozen=True)
class IdempotencyClaim:
    disposition: str
    operation: str
    key_sha256: str
    request_sha256: str
    response_status: int | None = None
    response_payload: dict[str, Any] | None = None
    state: str | None = None


class IdempotencyJournal:
    """Durable single-node idempotency journal with fail-closed ambiguous states.

    Raw idempotency keys are never persisted. A PENDING/AMBIGUOUS record is never
    automatically expired or retried because doing so could duplicate a side
    effect whose completion status is unknown after a process crash.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        default_state_dir = Path(os.environ.get("MORPHEUS_STATE_DIR", Path.home() / ".morpheus"))
        configured = os.environ.get("MORPHEUS_IDEMPOTENCY_DB_PATH")
        path = db_path if db_path is not None else configured or (default_state_dir / "idempotency.db")
        self.db_path = str(path)
        if self.db_path != ":memory:":
            Path(self.db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        if self.db_path != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA synchronous = FULL")
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS idempotency_records (
                    operation TEXT NOT NULL,
                    key_sha256 TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('PENDING', 'COMPLETED', 'AMBIGUOUS_FAILURE')),
                    response_status INTEGER,
                    response_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(operation, key_sha256)
                )
                """
            )
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_idempotency_state_updated ON idempotency_records(state, updated_at DESC)"
            )

    @staticmethod
    def _key_hash(key: str) -> str:
        canonical = validate_idempotency_key(key)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def claim(self, *, operation: str, key: str, request_digest: str) -> IdempotencyClaim:
        operation = operation.strip()
        if not operation or len(operation) > 128:
            raise ValueError("idempotency operation must contain 1-128 characters")
        if not _SHA256_RE.fullmatch(request_digest):
            raise ValueError("request_digest must be a lowercase SHA-256 identity")
        key_hash = self._key_hash(key)
        now = _utc_now()

        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT * FROM idempotency_records WHERE operation = ? AND key_sha256 = ?",
                (operation, key_hash),
            ).fetchone()
            if row is None:
                self._connection.execute(
                    """
                    INSERT INTO idempotency_records(
                        operation, key_sha256, request_sha256, state,
                        response_status, response_json, created_at, updated_at
                    ) VALUES(?, ?, ?, 'PENDING', NULL, NULL, ?, ?)
                    """,
                    (operation, key_hash, request_digest, now, now),
                )
                return IdempotencyClaim("NEW", operation, key_hash, request_digest, state="PENDING")

            if row["request_sha256"] != request_digest:
                return IdempotencyClaim(
                    "CONFLICT",
                    operation,
                    key_hash,
                    request_digest,
                    state=str(row["state"]),
                )
            state = str(row["state"])
            if state == "COMPLETED":
                payload = json.loads(row["response_json"]) if row["response_json"] else {}
                if not isinstance(payload, dict):
                    raise RuntimeError("idempotency journal contains non-object response payload")
                return IdempotencyClaim(
                    "REPLAY",
                    operation,
                    key_hash,
                    request_digest,
                    response_status=int(row["response_status"]),
                    response_payload=payload,
                    state=state,
                )
            if state == "AMBIGUOUS_FAILURE":
                return IdempotencyClaim("AMBIGUOUS", operation, key_hash, request_digest, state=state)
            return IdempotencyClaim("IN_PROGRESS", operation, key_hash, request_digest, state=state)

    def complete(
        self,
        *,
        operation: str,
        key_sha256: str,
        request_digest: str,
        status_code: int,
        response_payload: dict[str, Any],
    ) -> None:
        if not 100 <= status_code <= 599:
            raise ValueError("status_code must be an HTTP status")
        if not _SHA256_RE.fullmatch(key_sha256) or not _SHA256_RE.fullmatch(request_digest):
            raise ValueError("idempotency completion identities must be lowercase SHA-256 values")
        response_json = json.dumps(response_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        now = _utc_now()
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                UPDATE idempotency_records
                SET state = 'COMPLETED', response_status = ?, response_json = ?, updated_at = ?
                WHERE operation = ? AND key_sha256 = ? AND request_sha256 = ? AND state = 'PENDING'
                """,
                (status_code, response_json, now, operation, key_sha256, request_digest),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("idempotency completion lost its unique pending reservation")

    def mark_ambiguous_failure(
        self,
        *,
        operation: str,
        key_sha256: str,
        request_digest: str,
    ) -> None:
        now = _utc_now()
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                UPDATE idempotency_records
                SET state = 'AMBIGUOUS_FAILURE', response_status = NULL, response_json = NULL, updated_at = ?
                WHERE operation = ? AND key_sha256 = ? AND request_sha256 = ? AND state = 'PENDING'
                """,
                (now, operation, key_sha256, request_digest),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("idempotency ambiguous-failure transition lost its pending reservation")

    def release_pending_without_side_effect(
        self,
        *,
        operation: str,
        key_sha256: str,
        request_digest: str,
    ) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                DELETE FROM idempotency_records
                WHERE operation = ? AND key_sha256 = ? AND request_sha256 = ? AND state = 'PENDING'
                """,
                (operation, key_sha256, request_digest),
            )

    def verify_integrity(self) -> dict[str, Any]:
        with self._lock:
            quick_check = self._connection.execute("PRAGMA quick_check").fetchone()[0]
            rows = self._connection.execute(
                "SELECT state, COUNT(*) AS count FROM idempotency_records GROUP BY state"
            ).fetchall()
        counts = {state: 0 for state in sorted(_ALLOWED_STATES)}
        for row in rows:
            counts[str(row["state"])] = int(row["count"])
        valid = quick_check == "ok"
        return {
            "valid": valid,
            "database": "sqlite",
            "durable": self.db_path != ":memory:",
            "states": counts,
            "evidence_state": "IDEMPOTENCY_JOURNAL_INTEGRITY_OK" if valid else "IDEMPOTENCY_JOURNAL_INTEGRITY_FAILURE",
            "truth_boundary": (
                "The journal prevents automatic duplicate side effects for repeated keys on this single-node control plane. "
                "PENDING or AMBIGUOUS_FAILURE records intentionally require operator investigation rather than automatic expiry."
            ),
        }


JOURNAL = IdempotencyJournal()
