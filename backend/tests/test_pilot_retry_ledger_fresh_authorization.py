from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.pilot_retry_ledger_fresh_authorization import authorize_retry_from_fresh_verification


def h(ch: str) -> str:
    return ch * 64


def freshness(**overrides):
    data = dict(
        schema="morpheus-pilot-retry-ledger-verification-freshness-v1",
        operation="pilot.write",
        key_sha256=h("a"),
        request_sha256=h("b"),
        verification_sha256=h("c"),
        freshness_sha256=h("d"),
        disposition="RETRY_PENDING",
        verified_at_utc="2026-08-30T18:00:00Z",
        evaluated_at_utc="2026-08-30T18:00:30Z",
        max_age_seconds=60,
        fresh=True,
        retry_permitted=True,
        manual_resolution_required=False,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def test_fresh_retry_pending_produces_bounded_authorization():
    result = authorize_retry_from_fresh_verification(
        freshness(), authorization_policy_sha256=h("e"), authorized_at=datetime(2026, 8, 30, 18, 0, 45, tzinfo=timezone.utc)
    )
    assert result.retry_authorized is True
    assert result.manual_resolution_required is False
    assert result.authorization_expires_at_utc == "2026-08-30T18:01:00Z"
    assert len(result.authorization_sha256) == 64


def test_authorization_after_freshness_expiry_fails_closed():
    with pytest.raises(ValueError, match="expired"):
        authorize_retry_from_fresh_verification(
            freshness(), authorization_policy_sha256=h("e"), authorized_at=datetime(2026, 8, 30, 18, 1, 1, tzinfo=timezone.utc)
        )


def test_manual_or_non_retry_state_cannot_be_authorized():
    with pytest.raises(ValueError):
        authorize_retry_from_fresh_verification(
            freshness(retry_permitted=False, manual_resolution_required=True, fresh=False),
            authorization_policy_sha256=h("e"),
            authorized_at=datetime(2026, 8, 30, 18, 0, 45, tzinfo=timezone.utc),
        )
    with pytest.raises(ValueError):
        authorize_retry_from_fresh_verification(
            freshness(disposition="COMPLETED"), authorization_policy_sha256=h("e"), authorized_at=datetime(2026, 8, 30, 18, 0, 45, tzinfo=timezone.utc)
        )


def test_boolean_aliases_and_evidence_aliasing_fail_closed():
    with pytest.raises(ValueError):
        authorize_retry_from_fresh_verification(
            freshness(fresh=1), authorization_policy_sha256=h("e"), authorized_at=datetime(2026, 8, 30, 18, 0, 45, tzinfo=timezone.utc)
        )
    with pytest.raises(ValueError, match="independent"):
        authorize_retry_from_fresh_verification(
            freshness(), authorization_policy_sha256=h("d"), authorized_at=datetime(2026, 8, 30, 18, 0, 45, tzinfo=timezone.utc)
        )


def test_time_reversal_and_naive_authorization_fail_closed():
    with pytest.raises(ValueError, match="precede"):
        authorize_retry_from_fresh_verification(
            freshness(), authorization_policy_sha256=h("e"), authorized_at=datetime(2026, 8, 30, 18, 0, 29, tzinfo=timezone.utc)
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        authorize_retry_from_fresh_verification(
            freshness(), authorization_policy_sha256=h("e"), authorized_at=datetime(2026, 8, 30, 18, 0, 45)
        )
