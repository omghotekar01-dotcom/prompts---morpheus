from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.pilot_retry_budget_authorization import authorize_next_pilot_retry


def _receipt(**overrides):
    data = dict(
        schema="morpheus-pilot-retry-budget-receipt-v1",
        operation="pilot_synthesis_v1",
        key_sha256="1" * 64,
        request_sha256="2" * 64,
        budget_policy_sha256="3" * 64,
        execution_count=1,
        max_retry_executions=3,
        remaining_retry_executions=2,
        retry_budget_available=True,
        manual_resolution_required=False,
        evaluated_at="2026-08-30T12:00:00Z",
        receipt_sha256="4" * 64,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def test_authorization_is_deterministic_and_consumes_one_budget_slot():
    utc = datetime(2026, 8, 30, 12, 30, tzinfo=timezone.utc)
    ist = utc.astimezone(timezone(timedelta(hours=5, minutes=30)))
    a = authorize_next_pilot_retry(_receipt(), grant_policy_sha256="5" * 64, executor_sha256="6" * 64, granted_at=utc)
    b = authorize_next_pilot_retry(_receipt(), grant_policy_sha256="5" * 64, executor_sha256="6" * 64, granted_at=ist)
    assert a == b
    assert a.retry_authorized is True
    assert a.authorization_sequence == 2
    assert a.remaining_retry_executions_after_grant == 1
    assert a.granted_at == "2026-08-30T12:30:00Z"


def test_denies_exhausted_or_manual_resolution_budget_receipts():
    at = datetime(2026, 8, 30, 12, 30, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="does not authorize"):
        authorize_next_pilot_retry(_receipt(retry_budget_available=False, remaining_retry_executions=0, execution_count=3), grant_policy_sha256="5" * 64, executor_sha256="6" * 64, granted_at=at)
    with pytest.raises(ValueError, match="does not authorize"):
        authorize_next_pilot_retry(_receipt(retry_budget_available=False, manual_resolution_required=True), grant_policy_sha256="5" * 64, executor_sha256="6" * 64, granted_at=at)


def test_rejects_evidence_aliasing_and_boolean_aliases():
    at = datetime(2026, 8, 30, 12, 30, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="independent"):
        authorize_next_pilot_retry(_receipt(), grant_policy_sha256="4" * 64, executor_sha256="6" * 64, granted_at=at)
    with pytest.raises(ValueError, match="exact boolean"):
        authorize_next_pilot_retry(_receipt(retry_budget_available=1), grant_policy_sha256="5" * 64, executor_sha256="6" * 64, granted_at=at)


def test_rejects_bad_arithmetic_and_naive_time():
    at = datetime(2026, 8, 30, 12, 30, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="arithmetic"):
        authorize_next_pilot_retry(_receipt(remaining_retry_executions=1), grant_policy_sha256="5" * 64, executor_sha256="6" * 64, granted_at=at)
    with pytest.raises(ValueError, match="timezone-aware"):
        authorize_next_pilot_retry(_receipt(), grant_policy_sha256="5" * 64, executor_sha256="6" * 64, granted_at=datetime(2026, 8, 30, 12, 30))
