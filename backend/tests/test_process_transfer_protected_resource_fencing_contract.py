from __future__ import annotations

import pytest

from app.process_transfer_protected_resource_fencing import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    ProtectedResourceFencingDecision,
    _validate_consumer_decision,
)


def test_exact_consumer_decision_contract_accepts_only_matching_token_identity() -> None:
    decision = ProtectedResourceFencingDecision(
        resource_id="resource-a",
        fencing_authority_id="fence-a",
        fencing_counter=41,
        accepted=True,
    )

    assert (
        _validate_consumer_decision(
            decision,
            expected_resource_id="resource-a",
            expected_fencing_authority_id="fence-a",
            expected_fencing_counter=41,
        )
        is decision
    )


def test_boolean_counter_cannot_alias_integer_fencing_generation() -> None:
    decision = ProtectedResourceFencingDecision(
        resource_id="resource-a",
        fencing_authority_id="fence-a",
        fencing_counter=True,
        accepted=True,
    )

    with pytest.raises(ValueError, match="fencing_counter must be a non-negative integer"):
        _validate_consumer_decision(
            decision,
            expected_resource_id="resource-a",
            expected_fencing_authority_id="fence-a",
            expected_fencing_counter=1,
        )


@pytest.mark.parametrize("accepted", [1, 0, "true", None, object()])
def test_non_boolean_acceptance_cannot_authorize_protected_resource(accepted: object) -> None:
    decision = ProtectedResourceFencingDecision(
        resource_id="resource-a",
        fencing_authority_id="fence-a",
        fencing_counter=41,
        accepted=accepted,  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match="accepted must be boolean"):
        _validate_consumer_decision(
            decision,
            expected_resource_id="resource-a",
            expected_fencing_authority_id="fence-a",
            expected_fencing_counter=41,
        )


def test_explicit_false_acceptance_fails_closed() -> None:
    decision = ProtectedResourceFencingDecision(
        resource_id="resource-a",
        fencing_authority_id="fence-a",
        fencing_counter=41,
        accepted=False,
    )

    with pytest.raises(ValueError, match="protected resource rejected the fenced restart token"):
        _validate_consumer_decision(
            decision,
            expected_resource_id="resource-a",
            expected_fencing_authority_id="fence-a",
            expected_fencing_counter=41,
        )


def test_gate_state_and_truth_boundary_remain_non_activating() -> None:
    assert EVIDENCE_STATE.endswith("NO_CUTOVER_AUTHORITY")
    lowered = TRUTH_BOUNDARY.lower()
    assert "caller-supplied protected-resource token consumer" in lowered
    assert "does not prove its stale-token rejection semantics" in lowered
    assert "automatic control, activation" in lowered
    assert "traffic switching remain forbidden" in lowered
