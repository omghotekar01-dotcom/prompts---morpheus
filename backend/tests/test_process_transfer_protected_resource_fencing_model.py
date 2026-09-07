from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from app.process_transfer_protected_resource_fencing import ProtectedResourceFencingDecision
from app.process_transfer_protected_resource_fencing_model import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    InMemoryProtectedResourceFencingModel,
)


def test_first_newer_equal_and_stale_generations_have_explicit_state_semantics() -> None:
    model = InMemoryProtectedResourceFencingModel()

    first = model.validate_fencing_token("resource-a", "fence-a", 41)
    newer = model.validate_fencing_token("resource-a", "fence-a", 43)
    repeated = model.validate_fencing_token("resource-a", "fence-a", 43)
    stale = model.validate_fencing_token("resource-a", "fence-a", 42)

    assert first == ProtectedResourceFencingDecision("resource-a", "fence-a", 41, True)
    assert newer.accepted is True
    assert repeated.accepted is True
    assert stale.accepted is False
    state = model.snapshot("resource-a", "fence-a")
    assert state is not None
    assert state.highest_accepted_fencing_counter == 43


def test_stale_rejection_never_regresses_highest_generation() -> None:
    model = InMemoryProtectedResourceFencingModel()
    assert model.validate_fencing_token("resource-a", "fence-a", 90).accepted is True

    for counter in (89, 0, 72, 88):
        decision = model.validate_fencing_token("resource-a", "fence-a", counter)
        assert decision.accepted is False
        assert model.snapshot("resource-a", "fence-a").highest_accepted_fencing_counter == 90


def test_resource_and_authority_identity_pairs_are_isolated() -> None:
    model = InMemoryProtectedResourceFencingModel()
    assert model.validate_fencing_token("resource-a", "fence-a", 50).accepted is True

    assert model.validate_fencing_token("resource-b", "fence-a", 1).accepted is True
    assert model.validate_fencing_token("resource-a", "fence-b", 2).accepted is True

    assert model.snapshot("resource-a", "fence-a").highest_accepted_fencing_counter == 50
    assert model.snapshot("resource-b", "fence-a").highest_accepted_fencing_counter == 1
    assert model.snapshot("resource-a", "fence-b").highest_accepted_fencing_counter == 2


def test_concurrent_stale_generations_are_rejected_after_higher_generation_is_installed() -> None:
    model = InMemoryProtectedResourceFencingModel()
    assert model.validate_fencing_token("resource-a", "fence-a", 100).accepted is True

    with ThreadPoolExecutor(max_workers=16) as pool:
        decisions = list(
            pool.map(
                lambda counter: model.validate_fencing_token("resource-a", "fence-a", counter),
                range(100),
            )
        )

    assert decisions
    assert all(decision.accepted is False for decision in decisions)
    assert model.snapshot("resource-a", "fence-a").highest_accepted_fencing_counter == 100


def test_concurrent_equal_generation_replays_are_idempotently_accepted_without_advancing() -> None:
    model = InMemoryProtectedResourceFencingModel()
    assert model.validate_fencing_token("resource-a", "fence-a", 100).accepted is True

    with ThreadPoolExecutor(max_workers=16) as pool:
        decisions = list(
            pool.map(
                lambda _: model.validate_fencing_token("resource-a", "fence-a", 100),
                range(64),
            )
        )

    assert all(decision.accepted is True for decision in decisions)
    assert model.snapshot("resource-a", "fence-a").highest_accepted_fencing_counter == 100


def test_concurrent_newer_generations_leave_state_at_maximum_observed_generation() -> None:
    model = InMemoryProtectedResourceFencingModel()
    counters = list(range(101, 133))

    with ThreadPoolExecutor(max_workers=16) as pool:
        decisions = list(
            pool.map(
                lambda counter: model.validate_fencing_token("resource-a", "fence-a", counter),
                counters,
            )
        )

    assert len(decisions) == len(counters)
    assert model.snapshot("resource-a", "fence-a").highest_accepted_fencing_counter == max(counters)
    assert model.validate_fencing_token("resource-a", "fence-a", 132).accepted is True
    assert model.validate_fencing_token("resource-a", "fence-a", 131).accepted is False


@pytest.mark.parametrize(
    ("resource_id", "authority_id", "counter", "message"),
    [
        ("", "fence-a", 1, "resource_id"),
        ("   ", "fence-a", 1, "resource_id"),
        (None, "fence-a", 1, "resource_id"),
        ("resource-a", "", 1, "fencing_authority_id"),
        ("resource-a", None, 1, "fencing_authority_id"),
        ("resource-a", "fence-a", -1, "fencing_counter"),
        ("resource-a", "fence-a", True, "fencing_counter"),
        ("resource-a", "fence-a", 1.5, "fencing_counter"),
    ],
)
def test_invalid_inputs_fail_before_state_mutation(resource_id, authority_id, counter, message) -> None:
    model = InMemoryProtectedResourceFencingModel()
    with pytest.raises(ValueError, match=message):
        model.validate_fencing_token(resource_id, authority_id, counter)
    assert model.snapshot("resource-a", "fence-a") is None


def test_model_is_callback_compatible_with_e11_consumer_contract() -> None:
    model = InMemoryProtectedResourceFencingModel()
    callback = model.validate_fencing_token

    decision = callback("resource-a", "fence-a", 41)
    assert isinstance(decision, ProtectedResourceFencingDecision)
    assert decision == ProtectedResourceFencingDecision("resource-a", "fence-a", 41, True)


def test_model_never_grants_activation_or_traffic_authority() -> None:
    model = InMemoryProtectedResourceFencingModel()
    assert model.automatic_control_allowed is False
    assert model.activation_allowed is False
    assert model.traffic_switching_allowed is False
    assert EVIDENCE_STATE == "TESTABLE_PROTECTED_RESOURCE_FENCING_STATE_MODEL_NO_EXTERNAL_ATTESTATION"


def test_truth_boundary_denies_external_and_scientific_claims() -> None:
    lowered = TRUTH_BOUNDARY.lower()
    assert "in-process engineering reference model" in lowered
    assert "does not attest or prove" in lowered
    assert "cross-process or distributed linearizability" in lowered
    assert "no benchmark" in lowered
    assert "production-readiness claim" in lowered
