from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .process_transfer_protected_resource_fencing import ProtectedResourceFencingDecision


EVIDENCE_STATE = "TESTABLE_PROTECTED_RESOURCE_FENCING_STATE_MODEL_NO_EXTERNAL_ATTESTATION"
TRUTH_BOUNDARY = (
    "This module is an in-process engineering reference model for protected-resource fencing semantics. It serializes state "
    "transitions inside one Python process and rejects a fencing generation that is lower than the highest generation already "
    "accepted for the same protected-resource and fencing-authority identity pair. Equal generations are treated as idempotent "
    "replays and do not advance state. Resource and authority identities are isolated. This model does not attest or prove the "
    "behavior of an external database, filesystem, service, process, network, consensus system or production adapter; does not "
    "establish cross-process or distributed linearizability, durability, availability, authentication, compromise resistance, "
    "leases, locks, atomic cutover, live replacement, activation or traffic switching; and makes no benchmark, performance, "
    "novelty, scientific-effect, HA/SLA or production-readiness claim."
)


@dataclass(frozen=True)
class ProtectedResourceFencingState:
    resource_id: str
    fencing_authority_id: str
    highest_accepted_fencing_counter: int


class InMemoryProtectedResourceFencingModel:
    """Thread-safe in-process reference model for stale fencing-token rejection.

    Semantics for each exact ``(resource_id, fencing_authority_id)`` pair:
    - first valid generation is accepted and becomes the highest accepted generation;
    - a larger generation is accepted and advances the highest generation;
    - an equal generation is accepted as an idempotent replay without advancing state;
    - a smaller generation is rejected without mutating state.

    The lock makes those transitions atomic only with respect to threads sharing this exact model instance. That narrow property
    must not be generalized to external resources or distributed systems.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._highest_by_identity: dict[tuple[str, str], int] = {}

    @staticmethod
    def _require_identity(value: str, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")
        return value

    @staticmethod
    def _require_counter(value: int) -> int:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError("fencing_counter must be a non-negative integer")
        return value

    def validate_fencing_token(
        self,
        resource_id: str,
        fencing_authority_id: str,
        fencing_counter: int,
    ) -> ProtectedResourceFencingDecision:
        resource_id = self._require_identity(resource_id, "resource_id")
        fencing_authority_id = self._require_identity(fencing_authority_id, "fencing_authority_id")
        fencing_counter = self._require_counter(fencing_counter)
        key = (resource_id, fencing_authority_id)

        with self._lock:
            current = self._highest_by_identity.get(key)
            accepted = current is None or fencing_counter >= current
            if accepted and (current is None or fencing_counter > current):
                self._highest_by_identity[key] = fencing_counter

        return ProtectedResourceFencingDecision(
            resource_id=resource_id,
            fencing_authority_id=fencing_authority_id,
            fencing_counter=fencing_counter,
            accepted=accepted,
        )

    def snapshot(
        self,
        resource_id: str,
        fencing_authority_id: str,
    ) -> ProtectedResourceFencingState | None:
        resource_id = self._require_identity(resource_id, "resource_id")
        fencing_authority_id = self._require_identity(fencing_authority_id, "fencing_authority_id")
        key = (resource_id, fencing_authority_id)
        with self._lock:
            current = self._highest_by_identity.get(key)
        if current is None:
            return None
        return ProtectedResourceFencingState(
            resource_id=resource_id,
            fencing_authority_id=fencing_authority_id,
            highest_accepted_fencing_counter=current,
        )

    @property
    def automatic_control_allowed(self) -> bool:
        return False

    @property
    def activation_allowed(self) -> bool:
        return False

    @property
    def traffic_switching_allowed(self) -> bool:
        return False
