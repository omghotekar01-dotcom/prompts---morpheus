from datetime import datetime, timezone

import pytest

from app.pilot_idempotency_resolution_chain import verify_pilot_idempotency_resolution_chain
from app.pilot_idempotency_resolution_receipt import build_pilot_idempotency_resolution_receipt
from app.pilot_idempotency_retry_authorization import authorize_pilot_idempotent_retry


def _receipt(outcome="CONFIRMED_NO_SIDE_EFFECT", retry_allowed=True):
    state = "REMOVED_AFTER_CONFIRMED_NO_SIDE_EFFECT" if retry_allowed else "RESOLVED_SIDE_EFFECT_PRESENT"
    return build_pilot_idempotency_resolution_receipt({
        "schema": "morpheus-idempotency-operator-resolution-v1",
        "operation": "pilot_synthesis_v1",
        "key_sha256": "1" * 64,
        "request_sha256": "2" * 64,
        "outcome": outcome,
        "operator_id": "pilot.operator",
        "reason_sha256": "3" * 64,
        "resulting_state": state,
        "retry_allowed": retry_allowed,
        "authorization_evidence_hash": "4" * 64,
        "applied_evidence_hash": "5" * 64,
    }, exported_at=datetime(2026, 8, 30, 5, 0, tzinfo=timezone.utc))


def test_authorizes_only_verified_no_side_effect_chain():
    now = datetime(2026, 8, 30, 5, 1, tzinfo=timezone.utc)
    chain = verify_pilot_idempotency_resolution_chain([_receipt()], verified_at=now)
    result = authorize_pilot_idempotent_retry(
        chain, retry_request_sha256="6" * 64, executor_artifact_sha256="7" * 64, authorized_at=now
    )
    assert result.authorized is True
    assert result.operation == "pilot_synthesis_v1"


def test_rejects_chain_with_confirmed_side_effect():
    now = datetime(2026, 8, 30, 5, 1, tzinfo=timezone.utc)
    receipt = _receipt("CONFIRMED_SIDE_EFFECT_PRESENT", False)
    chain = verify_pilot_idempotency_resolution_chain([receipt], verified_at=now)
    with pytest.raises(ValueError, match="does not authorize retry"):
        authorize_pilot_idempotent_retry(
            chain, retry_request_sha256="6" * 64, executor_artifact_sha256="7" * 64, authorized_at=now
        )


def test_rejects_evidence_aliasing_and_naive_time():
    now = datetime(2026, 8, 30, 5, 1, tzinfo=timezone.utc)
    chain = verify_pilot_idempotency_resolution_chain([_receipt()], verified_at=now)
    with pytest.raises(ValueError, match="independent"):
        authorize_pilot_idempotent_retry(
            chain, retry_request_sha256="1" * 64, executor_artifact_sha256="7" * 64, authorized_at=now
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        authorize_pilot_idempotent_retry(
            chain, retry_request_sha256="6" * 64, executor_artifact_sha256="7" * 64,
            authorized_at=datetime(2026, 8, 30, 5, 1)
        )
