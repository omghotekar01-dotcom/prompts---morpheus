from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Protocol


EVIDENCE_STATE = "ATOMIC_CONDITIONAL_FENCING_BACKEND_CONTRACT_WITH_IN_MEMORY_REFERENCE_MODEL_NO_EXTERNAL_BACKEND_ATTESTATION"
TRUTH_BOUNDARY = (
    "This module defines MORPHEUS-side semantics for a versioned atomic conditional-write fencing backend and provides an in-memory "
    "reference model whose operations are serialized only inside one Python process. The contract makes predecessor version, exact "
    "resource/authority identity, stale rejection, equal-generation idempotence, newer-generation mutation and compare-and-swap "
    "conflict explicit. The in-memory model is test evidence for the state machine only. It does not attest any filesystem, database, "
    "cloud, network or distributed store; does not establish cross-process or distributed linearizability, durability, availability, "
    "consensus, leases, authentication, compromise resistance, protected-resource enforcement, safe cutover, activation or traffic "
    "switching; and makes no benchmark, performance, novelty, scientific-effect, HA/SLA or production-readiness claim."
)

_OUTCOMES = {"applied", "idempotent", "stale", "conflict"}


def _identity(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _counter(value: int, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _version(value: int | None, field: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{field} must be None or a positive integer")
    return value


@dataclass(frozen=True)
class AtomicFencingSnapshot:
    resource_id: str
    fencing_authority_id: str
    fencing_counter: int
    version: int


@dataclass(frozen=True)
class AtomicFencingTransitionResult:
    resource_id: str
    fencing_authority_id: str
    requested_fencing_counter: int
    expected_version: int | None
    observed_fencing_counter: int | None
    observed_version: int | None
    outcome: str
    accepted: bool
    state_changed: bool
    automatic_control_allowed: bool = False
    activation_allowed: bool = False
    traffic_switching_allowed: bool = False
    evidence_state: str = EVIDENCE_STATE
    truth_boundary: str = TRUTH_BOUNDARY


class AtomicConditionalFencingBackend(Protocol):
    def snapshot(self, resource_id: str, fencing_authority_id: str) -> AtomicFencingSnapshot | None: ...

    def conditional_write(
        self,
        resource_id: str,
        fencing_authority_id: str,
        fencing_counter: int,
        *,
        expected_version: int | None,
    ) -> AtomicFencingTransitionResult: ...


def validate_atomic_transition_result(
    result: object,
    *,
    resource_id: str,
    fencing_authority_id: str,
    requested_fencing_counter: int,
    expected_version: int | None,
) -> AtomicFencingTransitionResult:
    if not isinstance(result, AtomicFencingTransitionResult):
        raise ValueError("atomic fencing backend must return AtomicFencingTransitionResult")
    if result.resource_id != resource_id or result.fencing_authority_id != fencing_authority_id:
        raise ValueError("atomic fencing backend result identity mismatch")
    if result.requested_fencing_counter != requested_fencing_counter:
        raise ValueError("atomic fencing backend result requested counter mismatch")
    if result.expected_version != expected_version:
        raise ValueError("atomic fencing backend result predecessor version mismatch")
    if result.outcome not in _OUTCOMES:
        raise ValueError("atomic fencing backend result has unknown outcome")
    if not isinstance(result.accepted, bool) or not isinstance(result.state_changed, bool):
        raise ValueError("atomic fencing backend result flags must be boolean")
    _version(result.observed_version, "observed_version")
    if result.observed_fencing_counter is not None:
        _counter(result.observed_fencing_counter, "observed_fencing_counter")
    if result.automatic_control_allowed or result.activation_allowed or result.traffic_switching_allowed:
        raise ValueError("atomic fencing backend result attempted authority escalation")
    expected_flags = {
        "applied": (True, True),
        "idempotent": (True, False),
        "stale": (False, False),
        "conflict": (False, False),
    }[result.outcome]
    if (result.accepted, result.state_changed) != expected_flags:
        raise ValueError("atomic fencing backend result flags do not match outcome semantics")
    return result


class InMemoryAtomicConditionalFencingBackend:
    """Single-process reference model for the atomic conditional-write contract."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._states: dict[tuple[str, str], AtomicFencingSnapshot] = {}

    def snapshot(self, resource_id: str, fencing_authority_id: str) -> AtomicFencingSnapshot | None:
        key = (_identity(resource_id, "resource_id"), _identity(fencing_authority_id, "fencing_authority_id"))
        with self._lock:
            return self._states.get(key)

    def conditional_write(
        self,
        resource_id: str,
        fencing_authority_id: str,
        fencing_counter: int,
        *,
        expected_version: int | None,
    ) -> AtomicFencingTransitionResult:
        resource_id = _identity(resource_id, "resource_id")
        fencing_authority_id = _identity(fencing_authority_id, "fencing_authority_id")
        fencing_counter = _counter(fencing_counter, "fencing_counter")
        expected_version = _version(expected_version, "expected_version")
        key = (resource_id, fencing_authority_id)

        with self._lock:
            current = self._states.get(key)
            observed_counter = None if current is None else current.fencing_counter
            observed_version = None if current is None else current.version

            if current is not None and fencing_counter < current.fencing_counter:
                outcome = "stale"
            elif current is not None and fencing_counter == current.fencing_counter:
                outcome = "idempotent"
            elif observed_version != expected_version:
                outcome = "conflict"
            else:
                next_version = 1 if current is None else current.version + 1
                current = AtomicFencingSnapshot(resource_id, fencing_authority_id, fencing_counter, next_version)
                self._states[key] = current
                observed_counter = current.fencing_counter
                observed_version = current.version
                outcome = "applied"

            accepted = outcome in {"applied", "idempotent"}
            return AtomicFencingTransitionResult(
                resource_id=resource_id,
                fencing_authority_id=fencing_authority_id,
                requested_fencing_counter=fencing_counter,
                expected_version=expected_version,
                observed_fencing_counter=observed_counter,
                observed_version=observed_version,
                outcome=outcome,
                accepted=accepted,
                state_changed=outcome == "applied",
            )


def apply_fencing_token_with_atomic_backend(
    backend: AtomicConditionalFencingBackend,
    resource_id: str,
    fencing_authority_id: str,
    fencing_counter: int,
) -> AtomicFencingTransitionResult:
    """Apply one fencing token through the explicit versioned backend contract.

    A stale/equal decision from the backend is still validated as an exact backend statement. A newer write carries the exact version
    observed immediately before the call. A conflict is returned to the caller rather than silently retried, so retry policy cannot hide
    concurrent state movement. Backend exceptions are converted to fail-closed ValueError without authority escalation.
    """

    resource_id = _identity(resource_id, "resource_id")
    fencing_authority_id = _identity(fencing_authority_id, "fencing_authority_id")
    fencing_counter = _counter(fencing_counter, "fencing_counter")
    if backend is None:
        raise ValueError("atomic fencing backend is required")

    try:
        current = backend.snapshot(resource_id, fencing_authority_id)
    except Exception as exc:
        raise ValueError("atomic fencing backend snapshot failed") from exc

    if current is None:
        expected_version = None
    else:
        if not isinstance(current, AtomicFencingSnapshot):
            raise ValueError("atomic fencing backend snapshot must return AtomicFencingSnapshot or None")
        if current.resource_id != resource_id or current.fencing_authority_id != fencing_authority_id:
            raise ValueError("atomic fencing backend snapshot identity mismatch")
        _counter(current.fencing_counter, "snapshot fencing_counter")
        expected_version = _version(current.version, "snapshot version")

    try:
        result = backend.conditional_write(
            resource_id,
            fencing_authority_id,
            fencing_counter,
            expected_version=expected_version,
        )
    except Exception as exc:
        raise ValueError("atomic fencing backend conditional write failed") from exc

    return validate_atomic_transition_result(
        result,
        resource_id=resource_id,
        fencing_authority_id=fencing_authority_id,
        requested_fencing_counter=fencing_counter,
        expected_version=expected_version,
    )
