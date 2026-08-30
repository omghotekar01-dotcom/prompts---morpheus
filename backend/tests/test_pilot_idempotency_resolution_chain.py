from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.pilot_idempotency_resolution_chain import verify_pilot_idempotency_resolution_chain
from app.pilot_idempotency_resolution_receipt import build_pilot_idempotency_resolution_receipt


def _resolution(**overrides):
    value = {
        "schema": "morpheus-idempotency-operator-resolution-v1",
        "operation": "pilot_synthesis_v1",
        "key_sha256": "1" * 64,
        "request_sha256": "2" * 64,
        "outcome": "CONFIRMED_NO_SIDE_EFFECT",
        "operator_id": "pilot.operator",
        "reason_sha256": "3" * 64,
        "resulting_state": "REMOVED_AFTER_CONFIRMED_NO_SIDE_EFFECT",
        "retry_allowed": True,
        "authorization_evidence_hash": "4" * 64,
        "applied_evidence_hash": "5" * 64,
    }
    value.update(overrides)
    return value


def _receipt(at: datetime, **overrides):
    return build_pilot_idempotency_resolution_receipt(_resolution(**overrides), exported_at=at)


def test_chain_is_deterministic_and_timezone_canonical() -> None:
    t0 = datetime(2026, 8, 30, 4, 0, tzinfo=timezone.utc)
    receipt = _receipt(t0)
    shifted = t0.astimezone(timezone(timedelta(hours=5, minutes=30)))
    first = verify_pilot_idempotency_resolution_chain([receipt], verified_at=t0)
    second = verify_pilot_idempotency_resolution_chain([receipt], verified_at=shifted)
    assert first == second
    assert first.retry_allowed is True


def test_confirmed_side_effect_permanently_removes_retry_authority() -> None:
    t0 = datetime(2026, 8, 30, 4, 0, tzinfo=timezone.utc)
    side_effect = _receipt(
        t0,
        outcome="CONFIRMED_SIDE_EFFECT_PRESENT",
        resulting_state="RESOLVED_SIDE_EFFECT_PRESENT",
        retry_allowed=False,
    )
    chain = verify_pilot_idempotency_resolution_chain([side_effect], verified_at=t0)
    assert chain.retry_allowed is False


def test_chain_rejects_lineage_substitution_and_duplicate_receipts() -> None:
    t0 = datetime(2026, 8, 30, 4, 0, tzinfo=timezone.utc)
    first = _receipt(t0)
    second = _receipt(t0 + timedelta(seconds=1), request_sha256="6" * 64)
    with pytest.raises(ValueError, match="lineage changed"):
        verify_pilot_idempotency_resolution_chain([first, second], verified_at=t0)
    with pytest.raises(ValueError, match="unique"):
        verify_pilot_idempotency_resolution_chain([first, first], verified_at=t0)


def test_chain_rejects_time_reversal_and_empty_input() -> None:
    t0 = datetime(2026, 8, 30, 4, 0, tzinfo=timezone.utc)
    first = _receipt(t0 + timedelta(seconds=5), operator_id="pilot.operator.1")
    second = _receipt(t0, operator_id="pilot.operator.2", reason_sha256="6" * 64)
    with pytest.raises(ValueError, match="chronological"):
        verify_pilot_idempotency_resolution_chain([first, second], verified_at=t0)
    with pytest.raises(ValueError, match="at least one"):
        verify_pilot_idempotency_resolution_chain([], verified_at=t0)
