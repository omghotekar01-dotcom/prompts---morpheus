from __future__ import annotations

import hashlib
from pathlib import Path

from app.idempotency import IdempotencyJournal, request_sha256


KEY = "pilot-idempotency-key-0001"
OPERATION = "test_operation"


def _digest(value: str = "same") -> str:
    return request_sha256({"value": value})


def test_completed_record_replays_after_journal_reopen(tmp_path: Path) -> None:
    path = tmp_path / "idempotency.db"
    first = IdempotencyJournal(path)
    claim = first.claim(operation=OPERATION, key=KEY, request_digest=_digest())
    assert claim.disposition == "NEW"
    first.complete(
        operation=OPERATION,
        key_sha256=claim.key_sha256,
        request_digest=_digest(),
        status_code=200,
        response_payload={"run_id": "run-1", "ok": True},
    )

    reopened = IdempotencyJournal(path)
    replay = reopened.claim(operation=OPERATION, key=KEY, request_digest=_digest())
    assert replay.disposition == "REPLAY"
    assert replay.response_status == 200
    assert replay.response_payload == {"ok": True, "run_id": "run-1"}
    assert reopened.verify_integrity()["valid"] is True


def test_same_key_with_different_request_is_hard_conflict(tmp_path: Path) -> None:
    journal = IdempotencyJournal(tmp_path / "idempotency.db")
    first = journal.claim(operation=OPERATION, key=KEY, request_digest=_digest("a"))
    assert first.disposition == "NEW"
    conflict = journal.claim(operation=OPERATION, key=KEY, request_digest=_digest("b"))
    assert conflict.disposition == "CONFLICT"


def test_pending_and_ambiguous_records_never_auto_retry(tmp_path: Path) -> None:
    journal = IdempotencyJournal(tmp_path / "idempotency.db")
    first = journal.claim(operation=OPERATION, key=KEY, request_digest=_digest())
    assert journal.claim(operation=OPERATION, key=KEY, request_digest=_digest()).disposition == "IN_PROGRESS"

    journal.mark_ambiguous_failure(
        operation=OPERATION,
        key_sha256=first.key_sha256,
        request_digest=_digest(),
    )
    blocked = journal.claim(operation=OPERATION, key=KEY, request_digest=_digest())
    assert blocked.disposition == "AMBIGUOUS"
    integrity = journal.verify_integrity()
    assert integrity["states"]["AMBIGUOUS_FAILURE"] == 1
    assert "operator investigation" in integrity["truth_boundary"]


def test_pre_side_effect_release_allows_explicit_new_attempt(tmp_path: Path) -> None:
    journal = IdempotencyJournal(tmp_path / "idempotency.db")
    first = journal.claim(operation=OPERATION, key=KEY, request_digest=_digest())
    journal.release_pending_without_side_effect(
        operation=OPERATION,
        key_sha256=first.key_sha256,
        request_digest=_digest(),
    )
    second = journal.claim(operation=OPERATION, key=KEY, request_digest=_digest())
    assert second.disposition == "NEW"


def test_raw_idempotency_key_is_not_persisted_as_a_column_value(tmp_path: Path) -> None:
    journal = IdempotencyJournal(tmp_path / "idempotency.db")
    claim = journal.claim(operation=OPERATION, key=KEY, request_digest=_digest())
    with journal._lock:
        row = journal._connection.execute(
            "SELECT operation, key_sha256, request_sha256, state FROM idempotency_records"
        ).fetchone()
    assert row["key_sha256"] == hashlib.sha256(KEY.encode()).hexdigest()
    assert row["key_sha256"] != KEY
    assert KEY not in tuple(str(value) for value in row)
