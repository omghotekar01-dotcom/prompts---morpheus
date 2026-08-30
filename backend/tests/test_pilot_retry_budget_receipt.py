from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.pilot_retry_budget_receipt import issue_pilot_retry_budget_receipt


def _decision(**overrides):
    data = dict(
        schema="morpheus-pilot-retry-budget-decision-v1",
        operation="pilot_synthesis_v1",
        key_sha256="1" * 64,
        request_sha256="2" * 64,
        execution_count=1,
        max_retry_executions=3,
        remaining_retry_executions=2,
        retry_budget_available=True,
        manual_resolution_required=False,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def test_receipt_is_deterministic_and_normalizes_timezone():
    utc = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
    ist = utc.astimezone(timezone(timedelta(hours=5, minutes=30)))
    a = issue_pilot_retry_budget_receipt(_decision(), budget_policy_sha256="3" * 64, evaluated_at=utc)
    b = issue_pilot_retry_budget_receipt(_decision(), budget_policy_sha256="3" * 64, evaluated_at=ist)
    assert a == b
    assert a.evaluated_at == "2026-08-30T12:00:00Z"


def test_policy_changes_receipt_identity():
    at = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
    a = issue_pilot_retry_budget_receipt(_decision(), budget_policy_sha256="3" * 64, evaluated_at=at)
    b = issue_pilot_retry_budget_receipt(_decision(), budget_policy_sha256="4" * 64, evaluated_at=at)
    assert a.receipt_sha256 != b.receipt_sha256


def test_rejects_aliasing_and_inconsistent_budget_state():
    at = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="independent"):
        issue_pilot_retry_budget_receipt(_decision(), budget_policy_sha256="1" * 64, evaluated_at=at)
    with pytest.raises(ValueError, match="arithmetic"):
        issue_pilot_retry_budget_receipt(_decision(remaining_retry_executions=1), budget_policy_sha256="3" * 64, evaluated_at=at)
    with pytest.raises(ValueError, match="cannot be available"):
        issue_pilot_retry_budget_receipt(_decision(manual_resolution_required=True), budget_policy_sha256="3" * 64, evaluated_at=at)


def test_rejects_boolean_aliases_and_naive_time():
    at = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="exact boolean"):
        issue_pilot_retry_budget_receipt(_decision(retry_budget_available=1), budget_policy_sha256="3" * 64, evaluated_at=at)
    with pytest.raises(ValueError, match="timezone-aware"):
        issue_pilot_retry_budget_receipt(_decision(), budget_policy_sha256="3" * 64, evaluated_at=datetime(2026, 8, 30, 12, 0))
