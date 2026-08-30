from types import SimpleNamespace

import pytest

from app.pilot_retry_execution_ledger import build_retry_execution_ledger


def h(char: str) -> str:
    return char * 64


def receipt(sequence: int, outcome: str, second: int, receipt_char: str, **changes):
    data = dict(
        schema="morpheus-pilot-retry-execution-fence-v1",
        operation="migration-publish",
        key_sha256=h("1"),
        request_sha256=h("2"),
        authorization_sequence=sequence,
        outcome=outcome,
        executed_at_utc=f"2026-08-30T14:00:{second:02d}Z",
        authorization_consumed=True,
        retry_may_repeat_without_new_authorization=False,
        manual_resolution_required=outcome == "AMBIGUOUS",
        receipt_sha256=h(receipt_char),
    )
    data.update(changes)
    return SimpleNamespace(**data)


def test_failed_retry_can_progress_only_with_next_authorization_sequence():
    ledger = build_retry_execution_ledger([
        receipt(2, "FAILED_NO_SIDE_EFFECT", 1, "3"),
        receipt(3, "FAILED_NO_SIDE_EFFECT", 2, "4"),
    ])
    assert ledger.execution_count == 2
    assert ledger.terminal is False
    assert ledger.retry_requires_new_authorization is True
    assert ledger.last_authorization_sequence == 3


def test_success_is_terminal():
    ledger = build_retry_execution_ledger([receipt(2, "SUCCEEDED", 1, "3")])
    assert ledger.terminal is True
    assert ledger.manual_resolution_required is False
    with pytest.raises(ValueError, match="terminal outcome"):
        build_retry_execution_ledger([
            receipt(2, "SUCCEEDED", 1, "3"),
            receipt(3, "FAILED_NO_SIDE_EFFECT", 2, "4"),
        ])


def test_ambiguity_is_terminal_and_requires_manual_resolution():
    ledger = build_retry_execution_ledger([receipt(2, "AMBIGUOUS", 1, "3")])
    assert ledger.terminal is True
    assert ledger.manual_resolution_required is True
    assert ledger.retry_requires_new_authorization is False


def test_sequence_gaps_and_duplicate_receipts_fail_closed():
    with pytest.raises(ValueError, match="contiguous"):
        build_retry_execution_ledger([
            receipt(2, "FAILED_NO_SIDE_EFFECT", 1, "3"),
            receipt(4, "FAILED_NO_SIDE_EFFECT", 2, "4"),
        ])
    with pytest.raises(ValueError, match="duplicate"):
        build_retry_execution_ledger([
            receipt(2, "FAILED_NO_SIDE_EFFECT", 1, "3"),
            receipt(3, "FAILED_NO_SIDE_EFFECT", 2, "3"),
        ])


def test_lineage_time_and_boolean_aliasing_fail_closed():
    with pytest.raises(ValueError, match="lineage"):
        build_retry_execution_ledger([
            receipt(2, "FAILED_NO_SIDE_EFFECT", 1, "3"),
            receipt(3, "FAILED_NO_SIDE_EFFECT", 2, "4", request_sha256=h("9")),
        ])
    with pytest.raises(ValueError, match="strictly increasing"):
        build_retry_execution_ledger([
            receipt(2, "FAILED_NO_SIDE_EFFECT", 2, "3"),
            receipt(3, "FAILED_NO_SIDE_EFFECT", 1, "4"),
        ])
    with pytest.raises(ValueError, match="single-use"):
        build_retry_execution_ledger([receipt(2, "FAILED_NO_SIDE_EFFECT", 1, "3", authorization_consumed=1)])


def test_manual_resolution_flag_must_match_outcome():
    with pytest.raises(ValueError, match="manual-resolution"):
        build_retry_execution_ledger([receipt(2, "SUCCEEDED", 1, "3", manual_resolution_required=True)])
