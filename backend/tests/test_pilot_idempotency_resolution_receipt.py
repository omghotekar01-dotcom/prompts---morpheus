from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

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


def test_receipt_is_deterministic_and_timezone_canonical() -> None:
    instant = datetime(2026, 8, 30, 4, 0, tzinfo=timezone.utc)
    shifted = instant.astimezone(timezone(timedelta(hours=5, minutes=30)))
    first = build_pilot_idempotency_resolution_receipt(_resolution(), exported_at=instant)
    second = build_pilot_idempotency_resolution_receipt(_resolution(), exported_at=shifted)
    assert first == second
    assert first.exported_at_utc == "2026-08-30T04:00:00Z"
    assert len(first.receipt_sha256) == 64


def test_receipt_rejects_outcome_state_or_boolean_alias_mismatch() -> None:
    instant = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="state is inconsistent"):
        build_pilot_idempotency_resolution_receipt(
            _resolution(resulting_state="RESOLVED_SIDE_EFFECT_PRESENT"), exported_at=instant
        )
    with pytest.raises(ValueError, match="exact boolean"):
        build_pilot_idempotency_resolution_receipt(_resolution(retry_allowed=1), exported_at=instant)


def test_side_effect_present_is_permanently_non_retryable() -> None:
    receipt = build_pilot_idempotency_resolution_receipt(
        _resolution(
            outcome="CONFIRMED_SIDE_EFFECT_PRESENT",
            resulting_state="RESOLVED_SIDE_EFFECT_PRESENT",
            retry_allowed=False,
        ),
        exported_at=datetime.now(timezone.utc),
    )
    assert receipt.retry_allowed is False
    assert receipt.outcome == "CONFIRMED_SIDE_EFFECT_PRESENT"


def test_receipt_rejects_placeholder_alias_and_naive_time() -> None:
    aware = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="non-placeholder"):
        build_pilot_idempotency_resolution_receipt(_resolution(reason_sha256="0" * 64), exported_at=aware)
    with pytest.raises(ValueError, match="independent"):
        build_pilot_idempotency_resolution_receipt(
            _resolution(applied_evidence_hash="4" * 64), exported_at=aware
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        build_pilot_idempotency_resolution_receipt(_resolution(), exported_at=datetime(2026, 8, 30, 4, 0))


def test_content_change_changes_receipt_identity() -> None:
    instant = datetime.now(timezone.utc)
    first = build_pilot_idempotency_resolution_receipt(_resolution(), exported_at=instant)
    second = build_pilot_idempotency_resolution_receipt(
        _resolution(operator_id="pilot.operator.2"), exported_at=instant
    )
    assert first.receipt_sha256 != second.receipt_sha256
