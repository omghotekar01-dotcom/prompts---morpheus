from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from app.process_transfer_protected_resource_fencing_atomic import (
    AtomicFencingSnapshot,
    AtomicFencingTransitionResult,
    InMemoryAtomicConditionalFencingBackend,
    TRUTH_BOUNDARY,
    apply_fencing_token_with_atomic_backend,
)


def test_first_newer_equal_and_stale_semantics() -> None:
    backend = InMemoryAtomicConditionalFencingBackend()

    first = apply_fencing_token_with_atomic_backend(backend, "resource-a", "authority-a", 10)
    assert (first.outcome, first.accepted, first.state_changed, first.observed_version) == ("applied", True, True, 1)

    newer = apply_fencing_token_with_atomic_backend(backend, "resource-a", "authority-a", 12)
    assert (newer.outcome, newer.accepted, newer.state_changed, newer.observed_version) == ("applied", True, True, 2)

    equal = apply_fencing_token_with_atomic_backend(backend, "resource-a", "authority-a", 12)
    assert (equal.outcome, equal.accepted, equal.state_changed, equal.observed_version) == ("idempotent", True, False, 2)

    stale = apply_fencing_token_with_atomic_backend(backend, "resource-a", "authority-a", 11)
    assert (stale.outcome, stale.accepted, stale.state_changed, stale.observed_version) == ("stale", False, False, 2)
    assert backend.snapshot("resource-a", "authority-a") == AtomicFencingSnapshot("resource-a", "authority-a", 12, 2)


def test_predecessor_version_conflict_fails_without_mutation() -> None:
    backend = InMemoryAtomicConditionalFencingBackend()
    assert backend.conditional_write("resource-a", "authority-a", 5, expected_version=None).outcome == "applied"
    assert backend.conditional_write("resource-a", "authority-a", 6, expected_version=1).outcome == "applied"

    conflict = backend.conditional_write("resource-a", "authority-a", 7, expected_version=1)
    assert (conflict.outcome, conflict.accepted, conflict.state_changed) == ("conflict", False, False)
    assert backend.snapshot("resource-a", "authority-a") == AtomicFencingSnapshot("resource-a", "authority-a", 6, 2)


def test_equal_generation_is_retry_safe_even_if_predecessor_version_is_old() -> None:
    backend = InMemoryAtomicConditionalFencingBackend()
    assert backend.conditional_write("resource-a", "authority-a", 8, expected_version=None).outcome == "applied"
    assert backend.conditional_write("resource-a", "authority-a", 9, expected_version=1).outcome == "applied"

    replay = backend.conditional_write("resource-a", "authority-a", 9, expected_version=1)
    assert (replay.outcome, replay.accepted, replay.state_changed, replay.observed_version) == ("idempotent", True, False, 2)


def test_resource_and_authority_state_are_isolated() -> None:
    backend = InMemoryAtomicConditionalFencingBackend()
    assert apply_fencing_token_with_atomic_backend(backend, "resource-a", "authority-a", 4).accepted
    assert apply_fencing_token_with_atomic_backend(backend, "resource-b", "authority-a", 2).accepted
    assert apply_fencing_token_with_atomic_backend(backend, "resource-a", "authority-b", 7).accepted

    assert backend.snapshot("resource-a", "authority-a").fencing_counter == 4
    assert backend.snapshot("resource-b", "authority-a").fencing_counter == 2
    assert backend.snapshot("resource-a", "authority-b").fencing_counter == 7


def test_two_same_predecessor_newer_writes_cannot_both_apply() -> None:
    backend = InMemoryAtomicConditionalFencingBackend()
    assert backend.conditional_write("resource-a", "authority-a", 10, expected_version=None).outcome == "applied"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda counter: backend.conditional_write(
                    "resource-a", "authority-a", counter, expected_version=1
                ),
                [11, 12],
            )
        )

    assert sorted(result.outcome for result in results) == ["applied", "conflict"]
    snapshot = backend.snapshot("resource-a", "authority-a")
    assert snapshot.version == 2
    assert snapshot.fencing_counter in {11, 12}


def test_malformed_backend_snapshot_fails_closed_before_write() -> None:
    class Backend:
        writes = 0

        def snapshot(self, resource_id, fencing_authority_id):
            return object()

        def conditional_write(self, *args, **kwargs):
            self.writes += 1
            raise AssertionError("must not be called")

    backend = Backend()
    with pytest.raises(ValueError, match="snapshot must return"):
        apply_fencing_token_with_atomic_backend(backend, "resource-a", "authority-a", 1)
    assert backend.writes == 0


def test_malformed_backend_result_and_authority_escalation_fail_closed() -> None:
    class Backend:
        def __init__(self, result):
            self.result = result

        def snapshot(self, resource_id, fencing_authority_id):
            return None

        def conditional_write(self, *args, **kwargs):
            return self.result

    with pytest.raises(ValueError, match="must return AtomicFencingTransitionResult"):
        apply_fencing_token_with_atomic_backend(Backend(object()), "resource-a", "authority-a", 1)

    escalating = AtomicFencingTransitionResult(
        resource_id="resource-a",
        fencing_authority_id="authority-a",
        requested_fencing_counter=1,
        expected_version=None,
        observed_fencing_counter=1,
        observed_version=1,
        outcome="applied",
        accepted=True,
        state_changed=True,
        activation_allowed=True,
    )
    with pytest.raises(ValueError, match="authority escalation"):
        apply_fencing_token_with_atomic_backend(Backend(escalating), "resource-a", "authority-a", 1)


def test_backend_exceptions_are_wrapped_fail_closed() -> None:
    class SnapshotFailure:
        def snapshot(self, resource_id, fencing_authority_id):
            raise RuntimeError("offline")

    with pytest.raises(ValueError, match="snapshot failed"):
        apply_fencing_token_with_atomic_backend(SnapshotFailure(), "resource-a", "authority-a", 1)

    class WriteFailure:
        def snapshot(self, resource_id, fencing_authority_id):
            return None

        def conditional_write(self, *args, **kwargs):
            raise RuntimeError("conflict transport failure")

    with pytest.raises(ValueError, match="conditional write failed"):
        apply_fencing_token_with_atomic_backend(WriteFailure(), "resource-a", "authority-a", 1)


def test_input_types_and_truth_boundary_are_explicit() -> None:
    backend = InMemoryAtomicConditionalFencingBackend()
    for bad in (-1, True, 1.5):
        with pytest.raises(ValueError):
            apply_fencing_token_with_atomic_backend(backend, "resource-a", "authority-a", bad)

    with pytest.raises(ValueError):
        apply_fencing_token_with_atomic_backend(backend, "", "authority-a", 1)

    result = apply_fencing_token_with_atomic_backend(backend, "resource-a", "authority-a", 1)
    assert result.automatic_control_allowed is False
    assert result.activation_allowed is False
    assert result.traffic_switching_allowed is False
    assert "does not attest any filesystem, database, cloud, network or distributed store" in TRUTH_BOUNDARY
