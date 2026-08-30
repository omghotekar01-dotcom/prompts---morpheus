from types import SimpleNamespace

import pytest

from app.pilot_retry_budget import evaluate_pilot_retry_budget


def _history(*, count=1, outcome="FAILED_NO_SIDE_EFFECT", manual=False):
    return SimpleNamespace(
        schema="morpheus-pilot-retry-execution-history-v2",
        operation="pilot_synthesis_v1",
        key_sha256="1" * 64,
        request_sha256="2" * 64,
        execution_count=count,
        latest_outcome=outcome,
        manual_resolution_required=manual,
    )


def test_allows_retry_only_while_failed_no_side_effect_budget_remains():
    decision = evaluate_pilot_retry_budget(_history(count=1), max_retry_executions=3)
    assert decision.retry_budget_available is True
    assert decision.remaining_retry_executions == 2
    assert decision.manual_resolution_required is False


def test_exhaustion_requires_manual_resolution():
    decision = evaluate_pilot_retry_budget(_history(count=3), max_retry_executions=3)
    assert decision.retry_budget_available is False
    assert decision.remaining_retry_executions == 0
    assert decision.manual_resolution_required is True


def test_success_and_ambiguity_never_authorize_another_budget_retry():
    success = evaluate_pilot_retry_budget(_history(outcome="SUCCEEDED"), max_retry_executions=3)
    assert success.retry_budget_available is False
    ambiguous = evaluate_pilot_retry_budget(_history(outcome="AMBIGUOUS", manual=True), max_retry_executions=3)
    assert ambiguous.retry_budget_available is False
    assert ambiguous.manual_resolution_required is True


def test_rejects_invalid_budget_boolean_alias_and_inconsistent_state():
    with pytest.raises(ValueError, match="positive integer"):
        evaluate_pilot_retry_budget(_history(), max_retry_executions=True)
    with pytest.raises(ValueError, match="exceeds configured retry budget"):
        evaluate_pilot_retry_budget(_history(count=4), max_retry_executions=3)
    with pytest.raises(ValueError, match="inconsistent"):
        evaluate_pilot_retry_budget(_history(outcome="AMBIGUOUS", manual=False), max_retry_executions=3)
