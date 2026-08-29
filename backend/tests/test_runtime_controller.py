from __future__ import annotations

import pytest

from app.models import AccessDistribution, ObservedWorkloadSnapshot, QueryKind
from app.runtime import RuntimeController, workload_drift


def _snapshot(
    sequence: int,
    point: float,
    range_scan: float,
    access_distribution_mix: dict[AccessDistribution, float] | None = None,
) -> ObservedWorkloadSnapshot:
    return ObservedWorkloadSnapshot(
        operation_mix={
            QueryKind.POINT_LOOKUP: point,
            QueryKind.RANGE_SCAN: range_scan,
        },
        access_distribution_mix=access_distribution_mix or {},
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
    assert drift.operation_distance == 0.7
    assert drift.access_distribution_distance is None
    assert drift.method == "operation_mix_tv"
    assert drift.drifted
    assert "TV distance" in drift.explanation
    assert "telemetry" in drift.explanation


def test_distribution_only_drift_triggers_without_changing_operation_mix() -> None:
    operations = {QueryKind.POINT_LOOKUP: 0.9, QueryKind.RANGE_SCAN: 0.1}
    drift = workload_drift(
        operations,
        operations,
        threshold=0.2,
        baseline_access_distribution_mix={AccessDistribution.UNIFORM: 1.0},
        observed_access_distribution_mix={AccessDistribution.HOTSPOT: 1.0},
    )
    assert drift.operation_distance == 0.0
    assert drift.access_distribution_distance == 1.0
    assert drift.distance == 1.0
    assert drift.drifted
    assert drift.method == "max_component_tv"
    assert "access-distribution" in drift.explanation


def test_missing_distribution_telemetry_is_unknown_not_implicitly_uniform() -> None:
    operations = {QueryKind.POINT_LOOKUP: 1.0}
    drift = workload_drift(
        operations,
        operations,
        threshold=0.2,
        baseline_access_distribution_mix={AccessDistribution.HOTSPOT: 1.0},
        observed_access_distribution_mix=None,
    )
    assert drift.distance == 0.0
    assert drift.access_distribution_distance is None
    assert not drift.drifted
    assert "unavailable" in drift.explanation


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
    assert confirmed["previous_candidate_id"] == "candidate-a"
    assert confirmed["rollback_available"] is True

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


def test_runtime_controller_can_recommend_on_distribution_shift_alone() -> None:
    controller = RuntimeController()
    controller.start(
        "distribution-session",
        active_candidate_id="candidate-uniform",
        baseline=_snapshot(
            0,
            1.0,
            0.0,
            {AccessDistribution.UNIFORM: 1.0},
        ),
        drift_threshold=0.2,
        cooldown_windows=0,
    )
    decision, session = controller.observe(
        "distribution-session",
        snapshot=_snapshot(
            1,
            1.0,
            0.0,
            {AccessDistribution.HOTSPOT: 1.0},
        ),
        alternative_candidate_id="candidate-hotspot",
        current_predicted_latency_us=10.0,
        alternative_predicted_latency_us=4.0,
        estimated_switching_cost_us=1_000,
    )
    assert decision.drift is not None
    assert decision.drift.operation_distance == 0.0
    assert decision.drift.access_distribution_distance == 1.0
    assert decision.action == "SWITCH_RECOMMENDED"
    assert session["pending_candidate_id"] == "candidate-hotspot"


def test_confirmed_runtime_switch_can_be_rolled_back_once() -> None:
    controller = RuntimeController()
    controller.start(
        "rollback-session",
        active_candidate_id="candidate-a",
        baseline=_snapshot(
            0,
            0.9,
            0.1,
            {AccessDistribution.UNIFORM: 1.0},
        ),
        drift_threshold=0.2,
        cooldown_windows=0,
    )
    decision, _ = controller.observe(
        "rollback-session",
        snapshot=_snapshot(
            1,
            0.1,
            0.9,
            {AccessDistribution.HOTSPOT: 1.0},
        ),
        alternative_candidate_id="candidate-b",
        current_predicted_latency_us=10.0,
        alternative_predicted_latency_us=3.0,
        estimated_switching_cost_us=1_000,
    )
    assert decision.action == "SWITCH_RECOMMENDED"

    controller.confirm("rollback-session", candidate_id="candidate-b")
    rolled_back = controller.rollback_last_switch(
        "rollback-session",
        reason="post-switch health check failed",
    )
    assert rolled_back["active_candidate_id"] == "candidate-a"
    assert rolled_back["rollback_available"] is False
    assert rolled_back["previous_candidate_id"] is None
    assert rolled_back["baseline_operation_mix"]["point_lookup"] == pytest.approx(0.9)
    assert rolled_back["baseline_access_distribution_mix"]["uniform"] == pytest.approx(1.0)

    with pytest.raises(ValueError, match="no confirmed switch"):
        controller.rollback_last_switch("rollback-session", reason="second rollback")
