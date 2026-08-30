from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.pilot_retry_fresh_authorization_lease import issue_retry_execution_lease


def h(ch: str) -> str:
    return ch * 64


def authorization(**overrides):
    data = dict(
        schema="morpheus-pilot-retry-ledger-fresh-authorization-v1",
        operation="pilot.write",
        key_sha256=h("a"),
        request_sha256=h("b"),
        authorization_sha256=h("c"),
        authorized_at_utc="2026-08-30T18:00:45Z",
        authorization_expires_at_utc="2026-08-30T18:01:00Z",
        retry_authorized=True,
        manual_resolution_required=False,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def test_valid_fresh_authorization_yields_execution_lease():
    result = issue_retry_execution_lease(
        authorization(),
        lease_policy_sha256=h("d"),
        lease_sequence=1,
        leased_at=datetime(2026, 8, 30, 18, 0, 50, tzinfo=timezone.utc),
    )
    assert result.execution_permitted is True
    assert result.manual_resolution_required is False
    assert result.expires_at_utc == "2026-08-30T18:01:00Z"
    assert result.lease_sequence == 1
    assert len(result.lease_sha256) == 64


def test_expired_authorization_cannot_be_leased():
    with pytest.raises(ValueError, match="expired"):
        issue_retry_execution_lease(
            authorization(), lease_policy_sha256=h("d"), lease_sequence=1,
            leased_at=datetime(2026, 8, 30, 18, 1, 1, tzinfo=timezone.utc),
        )


def test_manual_resolution_and_boolean_aliases_fail_closed():
    with pytest.raises(ValueError):
        issue_retry_execution_lease(
            authorization(manual_resolution_required=True), lease_policy_sha256=h("d"), lease_sequence=1,
            leased_at=datetime(2026, 8, 30, 18, 0, 50, tzinfo=timezone.utc),
        )
    with pytest.raises(ValueError):
        issue_retry_execution_lease(
            authorization(retry_authorized=1), lease_policy_sha256=h("d"), lease_sequence=1,
            leased_at=datetime(2026, 8, 30, 18, 0, 50, tzinfo=timezone.utc),
        )
    with pytest.raises(ValueError, match="integer"):
        issue_retry_execution_lease(
            authorization(), lease_policy_sha256=h("d"), lease_sequence=True,
            leased_at=datetime(2026, 8, 30, 18, 0, 50, tzinfo=timezone.utc),
        )


def test_evidence_aliasing_and_time_reversal_fail_closed():
    with pytest.raises(ValueError, match="independent"):
        issue_retry_execution_lease(
            authorization(), lease_policy_sha256=h("c"), lease_sequence=1,
            leased_at=datetime(2026, 8, 30, 18, 0, 50, tzinfo=timezone.utc),
        )
    with pytest.raises(ValueError, match="precede"):
        issue_retry_execution_lease(
            authorization(), lease_policy_sha256=h("d"), lease_sequence=1,
            leased_at=datetime(2026, 8, 30, 18, 0, 44, tzinfo=timezone.utc),
        )


def test_naive_lease_time_fails_closed():
    with pytest.raises(ValueError, match="timezone-aware"):
        issue_retry_execution_lease(
            authorization(), lease_policy_sha256=h("d"), lease_sequence=1,
            leased_at=datetime(2026, 8, 30, 18, 0, 50),
        )
