from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.idempotency import IdempotencyJournal, request_sha256
from app.pilot_idempotency_resolution import resolve_idempotency_ambiguity
from app.storage import StateStore


KEY = "pilot-resolution-fixture-key"
OPERATION = "pilot_synthesis_v1"


def _stores(tmp_path: Path) -> tuple[StateStore, IdempotencyJournal, str, str]:
    store = StateStore(db_path=tmp_path / "morpheus.db", artifact_root=tmp_path / "artifacts")
    journal = IdempotencyJournal(tmp_path / "idempotency.db")
    digest = request_sha256({"fixture": "ambiguous"})
    claim = journal.claim(operation=OPERATION, key=KEY, request_digest=digest)
    journal.mark_ambiguous_failure(
        operation=OPERATION,
        key_sha256=claim.key_sha256,
        request_digest=digest,
    )
    return store, journal, claim.key_sha256, digest


def test_confirmed_existing_side_effect_becomes_permanently_blocked_and_audited(tmp_path: Path) -> None:
    store, journal, key_sha, digest = _stores(tmp_path)
    reason = "Run inventory and decision-certificate evidence confirm that the synthesis side effect exists."
    result = resolve_idempotency_ambiguity(
        store=store,
        journal=journal,
        operation=OPERATION,
        key_sha256=key_sha,
        request_sha256=digest,
        outcome="CONFIRMED_SIDE_EFFECT_PRESENT",
        operator_id="pilot.operator",
        reason=reason,
    )

    assert result["retry_allowed"] is False
    assert result["resulting_state"] == "RESOLVED_SIDE_EFFECT_PRESENT"
    status = journal.verify_integrity()
    assert status["states"]["AMBIGUOUS_FAILURE"] == 0
    assert status["states"]["RESOLVED_SIDE_EFFECT_PRESENT"] == 1
    assert journal.list_unresolved_ambiguities() == []

    blocked = journal.claim(operation=OPERATION, key=KEY, request_digest=digest)
    assert blocked.disposition == "RESOLVED_SIDE_EFFECT"
    assert blocked.state == "RESOLVED_SIDE_EFFECT_PRESENT"

    evidence = store.recent_evidence(limit=10)
    assert [item["kind"] for item in reversed(evidence)] == [
        "idempotency_operator_resolution_authorized",
        "idempotency_operator_resolution_applied",
    ]
    serialized = json.dumps(evidence, sort_keys=True)
    assert reason not in serialized
    assert hashlib.sha256(reason.encode()).hexdigest() in serialized
    assert store.verify_evidence_ledger()["valid"] is True


def test_confirmed_no_side_effect_removes_block_but_does_not_auto_retry(tmp_path: Path) -> None:
    store, journal, key_sha, digest = _stores(tmp_path)
    result = resolve_idempotency_ambiguity(
        store=store,
        journal=journal,
        operation=OPERATION,
        key_sha256=key_sha,
        request_sha256=digest,
        outcome="CONFIRMED_NO_SIDE_EFFECT",
        operator_id="pilot.operator",
        reason="State, artifact, and evidence inspection confirmed that no synthesis side effect was committed.",
    )

    assert result["retry_allowed"] is True
    assert result["resulting_state"] == "REMOVED_AFTER_CONFIRMED_NO_SIDE_EFFECT"
    status = journal.verify_integrity()
    assert status["states"]["AMBIGUOUS_FAILURE"] == 0
    assert status["states"]["PENDING"] == 0
    assert journal.list_unresolved_ambiguities() == []

    # The resolution itself does not retry anything. Only this explicit later
    # claim creates a fresh reservation for the same raw client key.
    explicit_retry = journal.claim(operation=OPERATION, key=KEY, request_digest=digest)
    assert explicit_retry.disposition == "NEW"
    assert store.verify_evidence_ledger()["entries"] == 2


def test_resolution_requires_exact_unresolved_identity_before_audit_mutation(tmp_path: Path) -> None:
    store, journal, key_sha, digest = _stores(tmp_path)
    with pytest.raises(ValueError, match="not exactly one unresolved"):
        resolve_idempotency_ambiguity(
            store=store,
            journal=journal,
            operation=OPERATION,
            key_sha256="f" * 64,
            request_sha256=digest,
            outcome="CONFIRMED_NO_SIDE_EFFECT",
            operator_id="pilot.operator",
            reason="Operator inspected the state and found no matching persisted side effect.",
        )
    assert store.verify_evidence_ledger()["entries"] == 0
    assert journal.verify_integrity()["states"]["AMBIGUOUS_FAILURE"] == 1


def test_reason_text_is_validated_and_never_required_in_journal_storage(tmp_path: Path) -> None:
    store, journal, key_sha, digest = _stores(tmp_path)
    with pytest.raises(ValueError, match="12-2000"):
        resolve_idempotency_ambiguity(
            store=store,
            journal=journal,
            operation=OPERATION,
            key_sha256=key_sha,
            request_sha256=digest,
            outcome="CONFIRMED_NO_SIDE_EFFECT",
            operator_id="pilot.operator",
            reason="too short",
        )
    with journal._lock:
        columns = [row[1] for row in journal._connection.execute("PRAGMA table_info(idempotency_resolutions)").fetchall()]
    assert "reason_sha256" in columns
    assert "reason" not in columns
