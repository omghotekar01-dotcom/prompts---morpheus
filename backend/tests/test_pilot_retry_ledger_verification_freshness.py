from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.pilot_retry_ledger_verification_freshness import evaluate_retry_ledger_verification_freshness


def h(ch: str) -> str:
    return ch * 64


def verification(disposition="RETRY_PENDING"):
    return SimpleNamespace(
        schema="morpheus-pilot-retry-ledger-seal-verification-v1",
        operation="pilot.write",
        key_sha256=h("a"),
        request_sha256=h("b"),
        verification_sha256=h("c"),
        disposition=disposition,
        verified_at_utc="2026-08-30T18:00:00Z",
        verified=True,
    )


def test_fresh_retry_pending_can_retry():
    result = evaluate_retry_ledger_verification_freshness(
        verification(), evaluated_at=datetime(2026, 8, 30, 18, 0, 30, tzinfo=timezone.utc), max_age_seconds=60
    )
    assert result.fresh is True
    assert result.retry_permitted is True
    assert result.manual_resolution_required is False


def test_stale_retry_pending_fails_closed_to_manual_resolution():
    result = evaluate_retry_ledger_verification_freshness(
        verification(), evaluated_at=datetime(2026, 8, 30, 18, 2, tzinfo=timezone.utc), max_age_seconds=60
    )
    assert result.fresh is False
    assert result.retry_permitted is False
    assert result.manual_resolution_required is True


def test_completed_never_retries():
    result = evaluate_retry_ledger_verification_freshness(
        verification("COMPLETED"), evaluated_at=datetime(2026, 8, 30, 18, 0, 1, tzinfo=timezone.utc), max_age_seconds=60
    )
    assert result.retry_permitted is False
    assert result.manual_resolution_required is False


def test_manual_resolution_remains_manual():
    result = evaluate_retry_ledger_verification_freshness(
        verification("MANUAL_RESOLUTION"), evaluated_at=datetime(2026, 8, 30, 18, 0, 1, tzinfo=timezone.utc), max_age_seconds=60
    )
    assert result.manual_resolution_required is True


def test_time_reversal_fails_closed():
    with pytest.raises(ValueError, match="precede"):
        evaluate_retry_ledger_verification_freshness(
            verification(), evaluated_at=datetime(2026, 8, 30, 17, 59, tzinfo=timezone.utc), max_age_seconds=60
        )


def test_boolean_alias_and_bad_age_fail_closed():
    bad = SimpleNamespace(**verification().__dict__)
    bad.verified = 1
    with pytest.raises(ValueError):
        evaluate_retry_ledger_verification_freshness(
            bad, evaluated_at=datetime(2026, 8, 30, 18, 0, 1, tzinfo=timezone.utc), max_age_seconds=60
        )
    with pytest.raises(ValueError):
        evaluate_retry_ledger_verification_freshness(
            verification(), evaluated_at=datetime(2026, 8, 30, 18, 0, 1, tzinfo=timezone.utc), max_age_seconds=True
        )
