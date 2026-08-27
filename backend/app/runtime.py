from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from threading import RLock
from typing import Any

from .models import AdaptationDecision, ObservedWorkloadSnapshot, QueryKind, WorkloadDrift


def _normalized_mix(mix: dict[QueryKind, float]) -> dict[QueryKind, float]:
    total = sum(mix.values())
    if total <= 0:
        return {}
    return {kind: value / total for kind, value in mix.items() if value > 0}


def workload_drift(
    baseline: dict[QueryKind, float],
    observed: dict[QueryKind, float],
    *,
    threshold: float = 0.18,
) -> WorkloadDrift:
    """Total-variation distance over normalized operation mixes.

    TV distance is bounded in [0, 1], deterministic, symmetric and easy to
    explain in a systems UI. More advanced distribution tests can be layered in
    later without changing the runtime-control contract.
    """

    if not 0 <= threshold <= 1:
        raise ValueError("drift threshold must be between 0 and 1")
    a = _normalized_mix(baseline)
    b = _normalized_mix(observed)
    kinds = set(a) | set(b)
    distance = 0.5 * sum(abs(a.get(kind, 0.0) - b.get(kind, 0.0)) for kind in kinds)
    drifted = distance >= threshold
    explanation = (
        f"operation-mix TV distance {distance:.4f} {'meets' if drifted else 'is below'} drift threshold {threshold:.4f}"
    )
    return WorkloadDrift(
        distance=round(distance, 6),
        threshold=round(threshold, 6),
        drifted=drifted,
        explanation=explanation,
    )


def decide_adaptation(
    snapshot: ObservedWorkloadSnapshot,
    *,
    current_predicted_latency_us: float,
    alternative_predicted_latency_us: float,
    estimated_switching_cost_us: float,
    lambda_factor: float = 1.5,
    safety_margin_ratio: float = 0.10,
    baseline_operation_mix: dict[QueryKind, float] | None = None,
    drift_threshold: float = 0.18,
    last_switch_sequence: int | None = None,
    cooldown_windows: int = 0,
) -> AdaptationDecision:
    if cooldown_windows < 0:
        raise ValueError("cooldown_windows cannot be negative")

    drift = None
    if baseline_operation_mix is not None:
        drift = workload_drift(baseline_operation_mix, snapshot.operation_mix, threshold=drift_threshold)

    cooldown_blocked = (
        last_switch_sequence is not None
        and snapshot.sequence <= last_switch_sequence + cooldown_windows
    )

    per_query_gain = max(current_predicted_latency_us - alternative_predicted_latency_us, 0.0)
    benefit = per_query_gain * snapshot.expected_future_queries
    threshold = lambda_factor * estimated_switching_cost_us * (1.0 + safety_margin_ratio)

    if cooldown_blocked:
        action = "RETAIN_COOLDOWN"
        reason = (
            f"Adaptation is inside the {cooldown_windows}-window cooldown after the last confirmed switch; "
            "candidate evaluation is recorded but no transition should be attempted."
        )
    elif drift is not None and not drift.drifted:
        action = "RETAIN_STABLE_WORKLOAD"
        reason = "Observed workload has not crossed the configured drift threshold."
    elif benefit > threshold and per_query_gain > 0:
        action = "SWITCH_RECOMMENDED"
        reason = (
            "Predicted cumulative benefit exceeds transition-cost threshold. "
            "This creates a pending recommendation only; it is not a completed hot-swap."
        )
    else:
        action = "RETAIN_CURRENT"
        reason = "Predicted benefit does not safely repay the estimated switching cost."

    return AdaptationDecision(
        action=action,
        predicted_benefit_us=round(benefit, 6),
        estimated_switching_cost_us=round(estimated_switching_cost_us, 6),
        threshold_us=round(threshold, 6),
        reason=reason,
        drift=drift,
        cooldown_blocked=cooldown_blocked,
    )


@dataclass
class _SessionRecord:
    session_id: str
    active_candidate_id: str
    baseline_operation_mix: dict[QueryKind, float]
    drift_threshold: float
    cooldown_windows: int
    last_switch_sequence: int | None = None
    last_observed_sequence: int | None = None
    pending_candidate_id: str | None = None
    pending_snapshot: ObservedWorkloadSnapshot | None = None
    previous_candidate_id: str | None = None
    previous_baseline_operation_mix: dict[QueryKind, float] | None = None
    previous_last_switch_sequence: int | None = None
    rollback_available: bool = False
    history: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=300))


class RuntimeController:
    """Two-phase runtime adaptation controller with control-plane rollback state.

    Observation can only create a pending recommendation. A separate explicit
    confirmation is required before the active candidate changes. Confirmation
    preserves the previous candidate/baseline so a later health or migration
    gate can authorize one control-plane rollback. None of these transitions
    claim that a live process pointer or data-plane object was swapped.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, _SessionRecord] = {}
        self._lock = RLock()

    def start(
        self,
        session_id: str,
        *,
        active_candidate_id: str,
        baseline: ObservedWorkloadSnapshot,
        drift_threshold: float = 0.18,
        cooldown_windows: int = 3,
    ) -> dict[str, Any]:
        if not session_id or len(session_id) > 128:
            raise ValueError("session_id must contain 1-128 characters")
        if not active_candidate_id:
            raise ValueError("active_candidate_id is required")
        if not 0 <= drift_threshold <= 1:
            raise ValueError("drift_threshold must be between 0 and 1")
        if cooldown_windows < 0:
            raise ValueError("cooldown_windows cannot be negative")

        with self._lock:
            if session_id in self._sessions:
                raise ValueError(f"runtime session already exists: {session_id}")
            record = _SessionRecord(
                session_id=session_id,
                active_candidate_id=active_candidate_id,
                baseline_operation_mix=dict(baseline.operation_mix),
                drift_threshold=drift_threshold,
                cooldown_windows=cooldown_windows,
                last_observed_sequence=baseline.sequence,
            )
            record.history.appendleft(
                {
                    "kind": "session_started",
                    "sequence": baseline.sequence,
                    "active_candidate_id": active_candidate_id,
                    "operation_mix": {kind.value: value for kind, value in baseline.operation_mix.items()},
                }
            )
            self._sessions[session_id] = record
            return self._view(record)

    def observe(
        self,
        session_id: str,
        *,
        snapshot: ObservedWorkloadSnapshot,
        alternative_candidate_id: str,
        current_predicted_latency_us: float,
        alternative_predicted_latency_us: float,
        estimated_switching_cost_us: float,
        lambda_factor: float = 1.5,
        safety_margin_ratio: float = 0.10,
    ) -> tuple[AdaptationDecision, dict[str, Any]]:
        with self._lock:
            record = self._require(session_id)
            if record.last_observed_sequence is not None and snapshot.sequence <= record.last_observed_sequence:
                raise ValueError(
                    f"snapshot sequence must increase monotonically; last={record.last_observed_sequence}, got={snapshot.sequence}"
                )

            decision = decide_adaptation(
                snapshot,
                current_predicted_latency_us=current_predicted_latency_us,
                alternative_predicted_latency_us=alternative_predicted_latency_us,
                estimated_switching_cost_us=estimated_switching_cost_us,
                lambda_factor=lambda_factor,
                safety_margin_ratio=safety_margin_ratio,
                baseline_operation_mix=record.baseline_operation_mix,
                drift_threshold=record.drift_threshold,
                last_switch_sequence=record.last_switch_sequence,
                cooldown_windows=record.cooldown_windows,
            )
            record.last_observed_sequence = snapshot.sequence
            if decision.action == "SWITCH_RECOMMENDED":
                record.pending_candidate_id = alternative_candidate_id
                record.pending_snapshot = snapshot

            record.history.appendleft(
                {
                    "kind": "observation",
                    "sequence": snapshot.sequence,
                    "alternative_candidate_id": alternative_candidate_id,
                    "decision": decision.model_dump(mode="json"),
                }
            )
            return decision, self._view(record)

    def confirm(self, session_id: str, *, candidate_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._require(session_id)
            if record.pending_candidate_id is None or record.pending_snapshot is None:
                raise ValueError("no pending adaptation recommendation exists")
            if candidate_id != record.pending_candidate_id:
                raise ValueError(
                    f"candidate {candidate_id} does not match pending recommendation {record.pending_candidate_id}"
                )

            previous = record.active_candidate_id
            record.previous_candidate_id = previous
            record.previous_baseline_operation_mix = dict(record.baseline_operation_mix)
            record.previous_last_switch_sequence = record.last_switch_sequence
            record.rollback_available = True

            record.active_candidate_id = candidate_id
            record.last_switch_sequence = record.pending_snapshot.sequence
            record.baseline_operation_mix = dict(record.pending_snapshot.operation_mix)
            record.pending_candidate_id = None
            record.pending_snapshot = None
            record.history.appendleft(
                {
                    "kind": "switch_confirmed",
                    "sequence": record.last_switch_sequence,
                    "previous_candidate_id": previous,
                    "active_candidate_id": candidate_id,
                    "evidence_state": "CONTROL_PLANE_STATE_CHANGE_ONLY",
                }
            )
            return self._view(record)

    def rollback_last_switch(self, session_id: str, *, reason: str) -> dict[str, Any]:
        """Restore the previous control-plane candidate after a confirmed switch.

        This intentionally represents authorization/state recovery only. A real
        deployment worker must separately restore the live data-plane handle.
        """

        with self._lock:
            record = self._require(session_id)
            if not reason:
                raise ValueError("rollback reason is required")
            if not record.rollback_available or record.previous_candidate_id is None:
                raise ValueError("no confirmed switch is available for rollback")
            if record.pending_candidate_id is not None:
                raise ValueError("cannot rollback while another adaptation recommendation is pending")

            failed_candidate = record.active_candidate_id
            restore_candidate = record.previous_candidate_id
            record.active_candidate_id = restore_candidate
            if record.previous_baseline_operation_mix is not None:
                record.baseline_operation_mix = dict(record.previous_baseline_operation_mix)
            record.last_switch_sequence = record.previous_last_switch_sequence
            record.previous_candidate_id = None
            record.previous_baseline_operation_mix = None
            record.previous_last_switch_sequence = None
            record.rollback_available = False
            record.history.appendleft(
                {
                    "kind": "switch_rolled_back",
                    "failed_candidate_id": failed_candidate,
                    "active_candidate_id": restore_candidate,
                    "reason": reason,
                    "evidence_state": "CONTROL_PLANE_ROLLBACK_ONLY",
                }
            )
            return self._view(record)

    def abort_pending(self, session_id: str, *, reason: str = "operator_or_verification_abort") -> dict[str, Any]:
        with self._lock:
            record = self._require(session_id)
            pending = record.pending_candidate_id
            record.pending_candidate_id = None
            record.pending_snapshot = None
            record.history.appendleft(
                {"kind": "switch_aborted", "pending_candidate_id": pending, "reason": reason}
            )
            return self._view(record)

    def get(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            return self._view(self._require(session_id))

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._view(self._sessions[key]) for key in sorted(self._sessions)]

    def _require(self, session_id: str) -> _SessionRecord:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise KeyError(f"unknown runtime session: {session_id}") from exc

    @staticmethod
    def _view(record: _SessionRecord) -> dict[str, Any]:
        return {
            "session_id": record.session_id,
            "active_candidate_id": record.active_candidate_id,
            "pending_candidate_id": record.pending_candidate_id,
            "previous_candidate_id": record.previous_candidate_id,
            "rollback_available": record.rollback_available,
            "baseline_operation_mix": {
                kind.value: value for kind, value in _normalized_mix(record.baseline_operation_mix).items()
            },
            "drift_threshold": record.drift_threshold,
            "cooldown_windows": record.cooldown_windows,
            "last_switch_sequence": record.last_switch_sequence,
            "last_observed_sequence": record.last_observed_sequence,
            "history": list(record.history),
            "evidence_state": "RUNTIME_CONTROL_PLANE_ONLY_NO_HOT_SWAP",
        }


RUNTIME = RuntimeController()
