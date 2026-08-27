from __future__ import annotations

from app.models import ObservedWorkloadSnapshot, QueryKind
from app.runtime import RuntimeController, workload_drift


def _snapshot(sequence: int, point: float, range_scan: float) -> ObservedWorkloadSnapshot:
    return ObservedWorkloadSnapshot(
        operation_mix={
            QueryKind.POINT_LOOKUP: point,
            QueryKind.RANGE_SCAN: range_scan,
        },
        expected_future_queries=100_000,
        sequence=sequence,
    )


def test_total_variation_drift_is_bounded_and_explainable() -> None:
    drift = workload_drift(
        {QueryKind.POINT_LOOKUP: 0.9, QueryKind.RANGE_SCAN: 0.1},
        {QueryKind.POINT_LOOKUP: 0.2, QueryKind.RANGE_SCAN: 0.8},
        threshold=0.2,
    )
    assert 0 <= drift.distance <= 1
    assert drift.distance == 0.7
    assert drift.drifted
    assert "TV distance" in drift.explanation


def test_runtime_controller_requires_drift_then_explicit_confirmation_and_cooldown() -> None:
    controller = RuntimeController()
    session = controller.start(
        "session-1",
        active_candidate_id="candidate-a",
        baseline=_snapshot(0, 0.9, 0.1),
        drift_threshold=0.2,
        cooldown_windows=3,
    )
    assert session["active_candidate_id"] == "candidate-a"
    assert session["pending_candidate_id"] is None

    stable_decision, stable_session = controller.observe(
        "session-1",
        snapshot=_snapshot(1, 0.85, 0.15),
        alternative_candidate_id="candidate-b",
        current_predicted_latency_us=10.0,
        alternative_predicted_latency_us=4.0,
        estimated_switching_cost_us=10_000,
    )
    assert stable_decision.action == "RETAIN_STABLE_WORKLOAD"
    assert stable_session["pending_candidate_id"] is None

    drift_decision, pending_session = controller.observe(
        "session-1",
        snapshot=_snapshot(2, 0.1, 0.9),
        alternative_candidate_id="candidate-b",
        current_predicted_latency_us=10.0,
        alternative_predicted_latency_us=4.0,
        estimated_switching_cost_us=10_000,
    )
    assert drift_decision.action == "SWITCH_RECOMMENDED"
    assert drift_decision.drift is not None and drift_decision.drift.drifted
    assert pending_session["active_candidate_id"] == "candidate-a"
    assert pending_session["pending_candidate_id"] == "candidate-b"

    confirmed = controller.confirm("session-1", candidate_id="candidate-b")
    assert confirmed["active_candidate_id"] == "candidate-b"
    assert confirmed["pending_candidate_id"] is None
    assert confirmed["last_switch_sequence"] == 2

    cooldown_decision, _ = controller.observe(
        "session-1",
        snapshot=_snapshot(3, 0.9, 0.1),
        alternative_candidate_id="candidate-c",
        current_predicted_latency_us=12.0,
        alternative_predicted_latency_us=3.0,
        estimated_switching_cost_us=1_000,
    )
    assert cooldown_decision.action == "RETAIN_COOLDOWN"
    assert cooldown_decision.cooldown_blocked
