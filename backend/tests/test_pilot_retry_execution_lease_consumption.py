from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.pilot_retry_execution_lease_consumption import consume_retry_execution_lease


def h(ch: str) -> str:
    return ch * 64


def lease(**overrides):
    data = dict(
        schema="morpheus-pilot-retry-fresh-authorization-lease-v1",
        operation="pilot.write",
        key_sha256=h("a"),
        request_sha256=h("b"),
        lease_sha256=h("c"),
        leased_at_utc="2026-08-30T18:00:50Z",
        expires_at_utc="2026-08-30T18:01:00Z",
        lease_sequence=1,
        execution_permitted=True,
        manual_resolution_required=False,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def test_fresh_lease_can_be_consumed_once():
    result = consume_retry_execution_lease(
        lease(), consumer_sha256=h("d"),
        consumed_at=datetime(2026, 8, 30, 18, 0, 55, tzinfo=timezone.utc),
    )
    assert result.execution_permitted is True
    assert result.manual_resolution_required is False
    assert result.lease_sequence == 1
    assert len(result.consumption_sha256) == 64


def test_expired_and_replayed_leases_fail_closed():
    with pytest.raises(ValueError, match="expired"):
        consume_retry_execution_lease(
            lease(), consumer_sha256=h("d"),
            consumed_at=datetime(2026, 8, 30, 18, 1, 1, tzinfo=timezone.utc),
        )
    prior = SimpleNamespace(lease_sha256=h("c"))
    with pytest.raises(ValueError, match="already been consumed"):
        consume_retry_execution_lease(
            lease(), consumer_sha256=h("d"),
            consumed_at=datetime(2026, 8, 30, 18, 0, 55, tzinfo=timezone.utc),
            prior_consumptions=[prior],
        )


def test_duplicate_history_and_aliases_fail_closed():
    duplicate = SimpleNamespace(lease_sha256=h("e"))
    with pytest.raises(ValueError, match="duplicate prior"):
        consume_retry_execution_lease(
            lease(), consumer_sha256=h("d"),
            consumed_at=datetime(2026, 8, 30, 18, 0, 55, tzinfo=timezone.utc),
            prior_consumptions=[duplicate, duplicate],
        )
    with pytest.raises(ValueError, match="independent"):
        consume_retry_execution_lease(
            lease(), consumer_sha256=h("c"),
            consumed_at=datetime(2026, 8, 30, 18, 0, 55, tzinfo=timezone.utc),
        )
    with pytest.raises(ValueError):
        consume_retry_execution_lease(
            lease(execution_permitted=1), consumer_sha256=h("d"),
            consumed_at=datetime(2026, 8, 30, 18, 0, 55, tzinfo=timezone.utc),
        )


def test_chronology_and_boolean_sequence_fail_closed():
    with pytest.raises(ValueError, match="precede"):
        consume_retry_execution_lease(
            lease(), consumer_sha256=h("d"),
            consumed_at=datetime(2026, 8, 30, 18, 0, 49, tzinfo=timezone.utc),
        )
    with pytest.raises(ValueError, match="integer"):
        consume_retry_execution_lease(
            lease(lease_sequence=True), consumer_sha256=h("d"),
            consumed_at=datetime(2026, 8, 30, 18, 0, 55, tzinfo=timezone.utc),
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        consume_retry_execution_lease(
            lease(), consumer_sha256=h("d"),
            consumed_at=datetime(2026, 8, 30, 18, 0, 55),
        )
