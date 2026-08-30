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
_PHYSICAL_STATES = {"PENDING", "COMPLETED", "AMBIGUOUS_FAILURE"}
_LOGICAL_STATES = (*sorted(_PHYSICAL_STATES), "RESOLVED_SIDE_EFFECT_PRESENT")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def request_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_idempotency_key(value: str) -> str:
    if not isinstance(value, str) or value != value.strip() or not _KEY_RE.fullmatch(value):
        raise ValueError("Idempotency-Key must be 8-128 canonical characters: letters, digits, '.', '_', ':', '-'")
    return value


def _validate_sha(value: str, name: str) -> str:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 identity")
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

    Manual resolution is deliberately separate from normal request processing.
    A confirmed existing side effect remains permanently blocked for the original
    key. A confirmed no-side-effect record may be deleted only through the audited
    operator-resolution workflow, after which a caller can explicitly retry.
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
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS idempotency_resolutions (
                    operation TEXT NOT NULL,
                    key_sha256 TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    resolution TEXT NOT NULL CHECK(resolution = 'CONFIRMED_SIDE_EFFECT_PRESENT'),
                    reason_sha256 TEXT NOT NULL,
                    resolved_at TEXT NOT NULL,
                    PRIMARY KEY(operation, key_sha256)
                )
                """
            )

    @staticmethod
    def _key_hash(key: str) -> str:
        canonical = validate_idempotency_key(key)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def claim(self, *, operation: str, key: str, request_digest: str) -> IdempotencyClaim:
        operation = operation.strip()
        if not operation or len(operation) > 128:
            raise ValueError("idempotency operation must contain 1-128 characters")
        _validate_sha(request_digest, "request_digest")
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
                resolution = self._connection.execute(
                    "SELECT resolution FROM idempotency_resolutions WHERE operation = ? AND key_sha256 = ?",
                    (operation, key_hash),
                ).fetchone()
                if resolution is not None and resolution["resolution"] == "CONFIRMED_SIDE_EFFECT_PRESENT":
                    return IdempotencyClaim(
                        "RESOLVED_SIDE_EFFECT",
                        operation,
                        key_hash,
                        request_digest,
                        state="RESOLVED_SIDE_EFFECT_PRESENT",
                    )
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
        _validate_sha(key_sha256, "key_sha256")
        _validate_sha(request_digest, "request_digest")
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

    def list_unresolved_ambiguities(self, *, limit: int = 50) -> list[dict[str, str]]:
        limit = min(max(int(limit), 1), 500)
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT r.operation, r.key_sha256, r.request_sha256, r.created_at, r.updated_at
                FROM idempotency_records r
                LEFT JOIN idempotency_resolutions z
                  ON z.operation = r.operation AND z.key_sha256 = r.key_sha256
                WHERE r.state = 'AMBIGUOUS_FAILURE' AND z.key_sha256 IS NULL
                ORDER BY r.updated_at ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def resolve_confirmed_side_effect_present(
        self,
        *,
        operation: str,
        key_sha256: str,
        request_digest: str,
        reason_sha256: str,
    ) -> None:
        _validate_sha(key_sha256, "key_sha256")
        _validate_sha(request_digest, "request_digest")
        _validate_sha(reason_sha256, "reason_sha256")
        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT state, request_sha256 FROM idempotency_records WHERE operation = ? AND key_sha256 = ?",
                (operation, key_sha256),
            ).fetchone()
            if row is None or row["state"] != "AMBIGUOUS_FAILURE" or row["request_sha256"] != request_digest:
                raise ValueError("operator resolution does not match an unresolved ambiguous idempotency record")
            existing = self._connection.execute(
                "SELECT request_sha256, resolution, reason_sha256 FROM idempotency_resolutions WHERE operation = ? AND key_sha256 = ?",
                (operation, key_sha256),
            ).fetchone()
            if existing is not None:
                if (
                    existing["request_sha256"] == request_digest
                    and existing["resolution"] == "CONFIRMED_SIDE_EFFECT_PRESENT"
                    and existing["reason_sha256"] == reason_sha256
                ):
                    return
                raise ValueError("a conflicting operator resolution already exists for this idempotency record")
            self._connection.execute(
                """
                INSERT INTO idempotency_resolutions(
                    operation, key_sha256, request_sha256, resolution, reason_sha256, resolved_at
                ) VALUES(?, ?, ?, 'CONFIRMED_SIDE_EFFECT_PRESENT', ?, ?)
                """,
                (operation, key_sha256, request_digest, reason_sha256, _utc_now()),
            )

    def resolve_confirmed_no_side_effect(
        self,
        *,
        operation: str,
        key_sha256: str,
        request_digest: str,
    ) -> None:
        _validate_sha(key_sha256, "key_sha256")
        _validate_sha(request_digest, "request_digest")
        with self._lock, self._connection:
            resolution = self._connection.execute(
                "SELECT resolution FROM idempotency_resolutions WHERE operation = ? AND key_sha256 = ?",
                (operation, key_sha256),
            ).fetchone()
            if resolution is not None:
                raise ValueError("cannot certify no side effect after a side-effect-present resolution")
            cursor = self._connection.execute(
                """
                DELETE FROM idempotency_records
                WHERE operation = ? AND key_sha256 = ? AND request_sha256 = ? AND state = 'AMBIGUOUS_FAILURE'
                """,
                (operation, key_sha256, request_digest),
            )
            if cursor.rowcount != 1:
                raise ValueError("operator resolution does not match an unresolved ambiguous idempotency record")

    def verify_integrity(self) -> dict[str, Any]:
        with self._lock:
            quick_check = self._connection.execute("PRAGMA quick_check").fetchone()[0]
            physical_rows = self._connection.execute(
                "SELECT state, COUNT(*) AS count FROM idempotency_records GROUP BY state"
            ).fetchall()
            resolved_row = self._connection.execute(
                "SELECT COUNT(*) AS count FROM idempotency_resolutions WHERE resolution = 'CONFIRMED_SIDE_EFFECT_PRESENT'"
            ).fetchone()
            unresolved_row = self._connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM idempotency_records r
                LEFT JOIN idempotency_resolutions z
                  ON z.operation = r.operation AND z.key_sha256 = r.key_sha256
                WHERE r.state = 'AMBIGUOUS_FAILURE' AND z.key_sha256 IS NULL
                """
            ).fetchone()
        physical = {state: 0 for state in sorted(_PHYSICAL_STATES)}
        for row in physical_rows:
            physical[str(row["state"])] = int(row["count"])
        counts = {state: 0 for state in _LOGICAL_STATES}
        counts["PENDING"] = physical["PENDING"]
        counts["COMPLETED"] = physical["COMPLETED"]
        counts["AMBIGUOUS_FAILURE"] = int(unresolved_row["count"])
        counts["RESOLVED_SIDE_EFFECT_PRESENT"] = int(resolved_row["count"])
        valid = quick_check == "ok" and physical["AMBIGUOUS_FAILURE"] == (
            counts["AMBIGUOUS_FAILURE"] + counts["RESOLVED_SIDE_EFFECT_PRESENT"]
        )
        return {
            "valid": valid,
            "database": "sqlite",
            "durable": self.db_path != ":memory:",
            "states": counts,
            "evidence_state": "IDEMPOTENCY_JOURNAL_INTEGRITY_OK" if valid else "IDEMPOTENCY_JOURNAL_INTEGRITY_FAILURE",
            "truth_boundary": (
                "The journal prevents automatic duplicate side effects for repeated keys on this single-node control plane. "
                "PENDING or unresolved AMBIGUOUS_FAILURE records are never automatically expired. A confirmed existing side effect "
                "remains permanently blocked for its original key rather than manufacturing a replay response."
            ),
        }


JOURNAL = IdempotencyJournal()
