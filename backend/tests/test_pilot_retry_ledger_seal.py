from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.pilot_retry_ledger_seal import seal_retry_execution_ledger


def h(ch: str) -> str:
    return ch * 64


def ledger(**overrides):
    values = dict(
        schema="morpheus-pilot-retry-execution-ledger-v1",
        operation="pilot.write",
        key_sha256=h("a"),
        request_sha256=h("b"),
        ledger_sha256=h("c"),
        terminal=False,
        manual_resolution_required=False,
        retry_requires_new_authorization=True,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_retry_pending_seal_is_deterministic():
    at = datetime(2026, 8, 30, 15, 30, tzinfo=timezone.utc)
    first = seal_retry_execution_ledger(ledger(), policy_sha256=h("d"), sealed_at=at)
    second = seal_retry_execution_ledger(ledger(), policy_sha256=h("d"), sealed_at=at)
    assert first.disposition == "RETRY_PENDING"
    assert first.seal_sha256 == second.seal_sha256


def test_terminal_success_seals_completed():
    result = seal_retry_execution_ledger(
        ledger(terminal=True, retry_requires_new_authorization=False),
        policy_sha256=h("d"),
        sealed_at=datetime.now(timezone.utc),
    )
    assert result.disposition == "COMPLETED"


def test_ambiguous_terminal_seals_manual_resolution():
    result = seal_retry_execution_ledger(
        ledger(terminal=True, manual_resolution_required=True, retry_requires_new_authorization=False),
        policy_sha256=h("d"),
        sealed_at=datetime.now(timezone.utc),
    )
    assert result.disposition == "MANUAL_RESOLUTION"


def test_contradictory_terminal_retry_fails_closed():
    with pytest.raises(ValueError):
        seal_retry_execution_ledger(ledger(terminal=True), policy_sha256=h("d"), sealed_at=datetime.now(timezone.utc))


def test_evidence_aliasing_fails_closed():
    with pytest.raises(ValueError):
        seal_retry_execution_ledger(ledger(ledger_sha256=h("d")), policy_sha256=h("d"), sealed_at=datetime.now(timezone.utc))


def test_naive_timestamp_fails_closed():
    with pytest.raises(ValueError):
        seal_retry_execution_ledger(ledger(), policy_sha256=h("d"), sealed_at=datetime(2026, 8, 30, 15, 30))
