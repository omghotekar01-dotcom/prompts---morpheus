from __future__ import annotations

import pytest

from app.adaptation_research import (
    AdaptationPhase,
    evaluate_immediate_switch,
    evaluate_never_switch,
    evaluate_offline_oracle,
    evaluate_transition_aware,
)


PHASES = [
    AdaptationPhase("point-heavy", queries=100, per_query_cost={"hash": 1.0, "tree": 3.0}),
    AdaptationPhase("range-heavy-short", queries=10, per_query_cost={"hash": 8.0, "tree": 2.0}),
    AdaptationPhase("range-heavy-long", queries=100, per_query_cost={"hash": 8.0, "tree": 2.0}),
]
TRANSITIONS = {
    ("hash", "tree"): 100.0,
    ("tree", "hash"): 100.0,
}


def test_transition_aware_policy_avoids_unprofitable_short_phase_then_switches_on_long_phase() -> None:
    never = evaluate_never_switch(PHASES, initial_candidate_id="hash")
    immediate = evaluate_immediate_switch(PHASES, initial_candidate_id="hash", transition_costs=TRANSITIONS)
    aware = evaluate_transition_aware(
        PHASES,
        initial_candidate_id="hash",
        transition_costs=TRANSITIONS,
        lambda_factor=1.0,
        safety_margin_ratio=0.0,
    )
    oracle = evaluate_offline_oracle(PHASES, initial_candidate_id="hash", transition_costs=TRANSITIONS)

    assert never.switches == 0
    assert immediate.switches == 1
    assert [step.candidate_id for step in immediate.steps] == ["hash", "tree", "tree"]
    assert [step.candidate_id for step in aware.steps] == ["hash", "hash", "tree"]
    assert aware.switches == 1
    assert aware.transition_cost == pytest.approx(100.0)
    assert aware.cumulative_cost < never.cumulative_cost
    assert oracle.cumulative_cost <= aware.cumulative_cost
    assert oracle.evidence_state == "EVALUATED_CALLER_SUPPLIED_PHASE_COSTS"


def test_immediate_switch_can_lose_when_phases_oscillate_below_break_even() -> None:
    phases = [
        AdaptationPhase("p1", 10, {"a": 1.0, "b": 5.0}),
        AdaptationPhase("p2", 10, {"a": 5.0, "b": 1.0}),
        AdaptationPhase("p3", 10, {"a": 1.0, "b": 5.0}),
        AdaptationPhase("p4", 10, {"a": 5.0, "b": 1.0}),
    ]
    transitions = {("a", "b"): 100.0, ("b", "a"): 100.0}

    never = evaluate_never_switch(phases, initial_candidate_id="a")
    immediate = evaluate_immediate_switch(phases, initial_candidate_id="a", transition_costs=transitions)
    aware = evaluate_transition_aware(
        phases,
        initial_candidate_id="a",
        transition_costs=transitions,
        lambda_factor=1.0,
        safety_margin_ratio=0.0,
    )

    assert immediate.switches == 3
    assert immediate.transition_cost == pytest.approx(300.0)
    assert immediate.cumulative_cost > never.cumulative_cost
    assert aware.switches == 0
    assert aware.cumulative_cost == pytest.approx(never.cumulative_cost)


def test_cooldown_blocks_immediate_reversal_even_when_phase_is_long() -> None:
    phases = [
        AdaptationPhase("p1", 100, {"a": 10.0, "b": 1.0}),
        AdaptationPhase("p2", 100, {"a": 1.0, "b": 10.0}),
        AdaptationPhase("p3", 100, {"a": 1.0, "b": 10.0}),
    ]
    transitions = {("a", "b"): 10.0, ("b", "a"): 10.0}
    report = evaluate_transition_aware(
        phases,
        initial_candidate_id="a",
        transition_costs=transitions,
        lambda_factor=1.0,
        safety_margin_ratio=0.0,
        cooldown_phases=1,
    )

    assert [step.candidate_id for step in report.steps] == ["b", "b", "a"]
    assert report.switches == 2


def test_offline_oracle_can_choose_to_switch_before_a_short_intermediate_phase() -> None:
    phases = [
        AdaptationPhase("start", 10, {"a": 1.0, "b": 10.0}),
        AdaptationPhase("middle", 10, {"a": 5.0, "b": 4.0}),
        AdaptationPhase("future", 1000, {"a": 10.0, "b": 1.0}),
    ]
    transitions = {("a", "b"): 20.0, ("b", "a"): 20.0}
    oracle = evaluate_offline_oracle(phases, initial_candidate_id="a", transition_costs=transitions)
    assert [step.candidate_id for step in oracle.steps] == ["a", "b", "b"]


def test_adaptation_evaluator_rejects_invalid_cost_data() -> None:
    with pytest.raises(ValueError):
        evaluate_never_switch([], initial_candidate_id="a")
    with pytest.raises(ValueError):
        evaluate_never_switch([AdaptationPhase("bad", 0, {"a": 1.0})], initial_candidate_id="a")
    with pytest.raises(ValueError):
        evaluate_immediate_switch(
            [AdaptationPhase("phase", 10, {"a": 1.0, "b": 0.5})],
            initial_candidate_id="a",
            transition_costs={},
        )
    with pytest.raises(ValueError):
        evaluate_transition_aware(
            [AdaptationPhase("phase", 10, {"a": 1.0})],
            initial_candidate_id="a",
            transition_costs={},
            cooldown_phases=-1,
        )
