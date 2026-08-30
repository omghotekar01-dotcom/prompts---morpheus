from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.pilot_retry_ledger_seal import seal_retry_execution_ledger
from app.pilot_retry_ledger_seal_verifier import verify_retry_ledger_seal
from types import SimpleNamespace


def h(ch: str) -> str:
    return ch * 64


def ledger():
    return SimpleNamespace(
        schema="morpheus-pilot-retry-execution-ledger-v1",
        operation="pilot.write",
        key_sha256=h("a"),
        request_sha256=h("b"),
        ledger_sha256=h("c"),
        terminal=False,
        manual_resolution_required=False,
        retry_requires_new_authorization=True,
    )


def make_seal():
    return seal_retry_execution_ledger(
        ledger(),
        policy_sha256=h("d"),
        sealed_at=datetime(2026, 8, 30, 16, 0, tzinfo=timezone.utc),
    )


def test_valid_seal_verifies_deterministically():
    at = datetime(2026, 8, 30, 16, 30, tzinfo=timezone.utc)
    first = verify_retry_ledger_seal(
        make_seal(),
        expected_operation="pilot.write",
        expected_key_sha256=h("a"),
        expected_request_sha256=h("b"),
        verified_at=at,
    )
    second = verify_retry_ledger_seal(
        make_seal(),
        expected_operation="pilot.write",
        expected_key_sha256=h("a"),
        expected_request_sha256=h("b"),
        verified_at=at,
    )
    assert first.verified is True
    assert first.disposition == "RETRY_PENDING"
    assert first.verification_sha256 == second.verification_sha256


def test_lineage_substitution_fails_closed():
    with pytest.raises(ValueError, match="lineage"):
        verify_retry_ledger_seal(
            make_seal(),
            expected_operation="pilot.write",
            expected_key_sha256=h("e"),
            expected_request_sha256=h("b"),
            verified_at=datetime.now(timezone.utc),
        )


def test_tampered_disposition_fails_closed():
    with pytest.raises(ValueError):
        verify_retry_ledger_seal(
            replace(make_seal(), disposition="COMPLETED"),
            expected_operation="pilot.write",
            expected_key_sha256=h("a"),
            expected_request_sha256=h("b"),
            verified_at=datetime.now(timezone.utc),
        )


def test_tampered_digest_fails_closed():
    with pytest.raises(ValueError, match="digest mismatch"):
        verify_retry_ledger_seal(
            replace(make_seal(), seal_sha256=h("f")),
            expected_operation="pilot.write",
            expected_key_sha256=h("a"),
            expected_request_sha256=h("b"),
            verified_at=datetime.now(timezone.utc),
        )


def test_boolean_alias_fails_closed():
    with pytest.raises(ValueError):
        verify_retry_ledger_seal(
            replace(make_seal(), terminal=1),
            expected_operation="pilot.write",
            expected_key_sha256=h("a"),
            expected_request_sha256=h("b"),
            verified_at=datetime.now(timezone.utc),
        )


def test_naive_verification_time_fails_closed():
    with pytest.raises(ValueError):
        verify_retry_ledger_seal(
            make_seal(),
            expected_operation="pilot.write",
            expected_key_sha256=h("a"),
            expected_request_sha256=h("b"),
            verified_at=datetime(2026, 8, 30, 16, 30),
        )
