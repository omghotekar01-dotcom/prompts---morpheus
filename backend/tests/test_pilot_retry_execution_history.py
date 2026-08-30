from types import SimpleNamespace

import pytest

from app.pilot_retry_execution_history import validate_pilot_retry_execution_history


def _receipt(*, grant: str, receipt: str, outcome: str = "SUCCEEDED", key: str = "1" * 64, request: str = "2" * 64):
    return SimpleNamespace(
        schema="morpheus-pilot-idempotency-retry-execution-receipt-v1",
        operation="pilot_synthesis_v1",
        key_sha256=key,
        request_sha256=request,
        authorization_sha256=grant,
        receipt_sha256=receipt,
        retry_consumed=True,
        outcome=outcome,
        follow_up_resolution_required=outcome == "AMBIGUOUS",
    )


def test_accepts_independent_single_use_retry_receipts():
    result = validate_pilot_retry_execution_history([
        _receipt(grant="3" * 64, receipt="4" * 64),
        _receipt(grant="5" * 64, receipt="6" * 64, outcome="FAILED_NO_SIDE_EFFECT"),
    ])
    assert result.schema.endswith("v2")
    assert result.execution_count == 2
    assert result.manual_resolution_required is False


def test_rejects_reused_retry_grant():
    with pytest.raises(ValueError, match="cannot be consumed twice"):
        validate_pilot_retry_execution_history([
            _receipt(grant="3" * 64, receipt="4" * 64),
            _receipt(grant="3" * 64, receipt="6" * 64),
        ])


def test_ambiguous_execution_must_be_terminal():
    with pytest.raises(ValueError, match="terminal"):
        validate_pilot_retry_execution_history([
            _receipt(grant="3" * 64, receipt="4" * 64, outcome="AMBIGUOUS"),
            _receipt(grant="5" * 64, receipt="6" * 64),
        ])


def test_terminal_ambiguity_requires_manual_resolution():
    result = validate_pilot_retry_execution_history([
        _receipt(grant="3" * 64, receipt="4" * 64, outcome="AMBIGUOUS"),
    ])
    assert result.manual_resolution_required is True
    assert result.ambiguous_count == 1


def test_rejects_non_hex_digest_and_unknown_outcome():
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        validate_pilot_retry_execution_history([_receipt(grant="g" * 64, receipt="4" * 64)])
    with pytest.raises(ValueError, match="unsupported retry execution outcome"):
        validate_pilot_retry_execution_history([_receipt(grant="3" * 64, receipt="4" * 64, outcome="MAYBE")])


def test_rejects_aliased_evidence_identities():
    with pytest.raises(ValueError, match="independent"):
        validate_pilot_retry_execution_history([
            _receipt(grant="3" * 64, receipt="4" * 64, key="2" * 64, request="2" * 64)
        ])
    with pytest.raises(ValueError, match="independent"):
        validate_pilot_retry_execution_history([_receipt(grant="1" * 64, receipt="4" * 64)])
