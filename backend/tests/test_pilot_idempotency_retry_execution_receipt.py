from datetime import datetime, timezone

import pytest

from app.pilot_idempotency_resolution_chain import verify_pilot_idempotency_resolution_chain
from app.pilot_idempotency_resolution_receipt import build_pilot_idempotency_resolution_receipt
from app.pilot_idempotency_retry_authorization import authorize_pilot_idempotent_retry
from app.pilot_idempotency_retry_execution_receipt import record_pilot_idempotent_retry_execution


def _authorization():
    resolution = build_pilot_idempotency_resolution_receipt({
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
    }, exported_at=datetime(2026, 8, 30, 5, 0, tzinfo=timezone.utc))
    chain = verify_pilot_idempotency_resolution_chain(
        [resolution], verified_at=datetime(2026, 8, 30, 5, 1, tzinfo=timezone.utc)
    )
    return authorize_pilot_idempotent_retry(
        chain,
        retry_request_sha256="6" * 64,
        executor_artifact_sha256="7" * 64,
        authorized_at=datetime(2026, 8, 30, 5, 2, tzinfo=timezone.utc),
    )


def test_records_single_use_success_receipt_deterministically():
    auth = _authorization()
    now = datetime(2026, 8, 30, 5, 3, tzinfo=timezone.utc)
    one = record_pilot_idempotent_retry_execution(
        auth, execution_evidence_sha256="8" * 64, result_artifact_sha256="9" * 64,
        outcome="SUCCEEDED", executed_at=now,
    )
    two = record_pilot_idempotent_retry_execution(
        auth, execution_evidence_sha256="8" * 64, result_artifact_sha256="9" * 64,
        outcome="SUCCEEDED", executed_at=now,
    )
    assert one == two
    assert one.retry_consumed is True
    assert one.follow_up_resolution_required is False


def test_ambiguous_execution_requires_resolution_and_still_consumes_retry():
    result = record_pilot_idempotent_retry_execution(
        _authorization(), execution_evidence_sha256="8" * 64, result_artifact_sha256="9" * 64,
        outcome="AMBIGUOUS", executed_at=datetime(2026, 8, 30, 5, 3, tzinfo=timezone.utc),
    )
    assert result.retry_consumed is True
    assert result.follow_up_resolution_required is True


def test_rejects_aliasing_invalid_outcome_and_naive_time():
    auth = _authorization()
    now = datetime(2026, 8, 30, 5, 3, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="independent"):
        record_pilot_idempotent_retry_execution(
            auth, execution_evidence_sha256="6" * 64, result_artifact_sha256="9" * 64,
            outcome="SUCCEEDED", executed_at=now,
        )
    with pytest.raises(ValueError, match="outcome"):
        record_pilot_idempotent_retry_execution(
            auth, execution_evidence_sha256="8" * 64, result_artifact_sha256="9" * 64,
            outcome="RETRY_AGAIN", executed_at=now,
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        record_pilot_idempotent_retry_execution(
            auth, execution_evidence_sha256="8" * 64, result_artifact_sha256="9" * 64,
            outcome="SUCCEEDED", executed_at=datetime(2026, 8, 30, 5, 3),
        )
