from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.pilot_retry_execution_fence import fence_retry_execution


def h(char: str) -> str:
    return char * 64


def auth(**changes):
    data = dict(
        schema="morpheus-pilot-retry-budget-authorization-v1",
        operation="migration-publish",
        key_sha256=h("1"),
        request_sha256=h("2"),
        authorization_sha256=h("3"),
        authorization_sequence=2,
        retry_authorized=True,
    )
    data.update(changes)
    return SimpleNamespace(**data)


def registry(**changes):
    data = dict(
        schema="morpheus-pilot-retry-authorization-registry-v1",
        operation="migration-publish",
        key_sha256=h("1"),
        request_sha256=h("2"),
        authorization_sha256=h("3"),
        authorization_sequence=2,
        authorization_consumed=True,
        registry_sha256=h("4"),
    )
    data.update(changes)
    return SimpleNamespace(**data)


def test_execution_is_bound_and_never_reuses_consumed_grant():
    receipt = fence_retry_execution(
        auth(), registry(), executor_sha256=h("5"), outcome="SUCCEEDED", executed_at=datetime(2026, 8, 30, 14, 0, tzinfo=timezone.utc)
    )
    assert receipt.authorization_consumed is True
    assert receipt.retry_may_repeat_without_new_authorization is False
    assert receipt.manual_resolution_required is False


def test_ambiguous_outcome_forces_manual_resolution():
    receipt = fence_retry_execution(
        auth(), registry(), executor_sha256=h("5"), outcome="AMBIGUOUS", executed_at=datetime.now(timezone.utc)
    )
    assert receipt.manual_resolution_required is True


def test_unconsumed_authorization_cannot_execute():
    with pytest.raises(ValueError, match="consumed before execution"):
        fence_retry_execution(auth(), registry(authorization_consumed=False), executor_sha256=h("5"), outcome="SUCCEEDED", executed_at=datetime.now(timezone.utc))


def test_lineage_substitution_is_rejected():
    with pytest.raises(ValueError, match="lineage"):
        fence_retry_execution(auth(), registry(request_sha256=h("6")), executor_sha256=h("5"), outcome="SUCCEEDED", executed_at=datetime.now(timezone.utc))


def test_evidence_aliasing_is_rejected():
    with pytest.raises(ValueError, match="independent"):
        fence_retry_execution(auth(), registry(), executor_sha256=h("4"), outcome="SUCCEEDED", executed_at=datetime.now(timezone.utc))


def test_naive_time_and_unknown_outcome_are_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        fence_retry_execution(auth(), registry(), executor_sha256=h("5"), outcome="SUCCEEDED", executed_at=datetime(2026, 8, 30, 14, 0))
    with pytest.raises(ValueError, match="unsupported"):
        fence_retry_execution(auth(), registry(), executor_sha256=h("5"), outcome="MAYBE", executed_at=datetime.now(timezone.utc))
