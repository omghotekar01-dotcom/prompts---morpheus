from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class AdaptationPhase:
    phase_id: str
    queries: int
    per_query_cost: Mapping[str, float]

    def validate(self) -> None:
        if not self.phase_id.strip():
            raise ValueError("phase_id cannot be empty")
        if self.queries <= 0:
            raise ValueError("phase queries must be positive")
        if not self.per_query_cost:
            raise ValueError("phase must provide at least one candidate cost")
        for candidate, raw_cost in self.per_query_cost.items():
            if not str(candidate).strip():
                raise ValueError("candidate ids cannot be empty")
            cost = float(raw_cost)
            if not math.isfinite(cost) or cost < 0:
                raise ValueError("per-query costs must be finite and non-negative")


@dataclass(frozen=True)
class AdaptationStep:
    phase_id: str
    candidate_id: str
    execution_cost: float
    transition_cost: float
    switched: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "phase_id": self.phase_id,
            "candidate_id": self.candidate_id,
            "execution_cost": self.execution_cost,
            "transition_cost": self.transition_cost,
            "switched": self.switched,
        }


@dataclass(frozen=True)
class AdaptationPolicyResult:
    policy: str
    initial_candidate_id: str
    final_candidate_id: str
    execution_cost: float
    transition_cost: float
    cumulative_cost: float
    switches: int
    steps: tuple[AdaptationStep, ...]
    evidence_state: str = "EVALUATED_CALLER_SUPPLIED_PHASE_COSTS"

    def as_dict(self) -> dict[str, object]:
        return {
            "policy": self.policy,
            "initial_candidate_id": self.initial_candidate_id,
            "final_candidate_id": self.final_candidate_id,
            "execution_cost": self.execution_cost,
            "transition_cost": self.transition_cost,
            "cumulative_cost": self.cumulative_cost,
            "switches": self.switches,
            "steps": [step.as_dict() for step in self.steps],
            "evidence_state": self.evidence_state,
            "truth_note": (
                "This evaluator consumes caller-supplied measured or otherwise explicitly labelled phase/transition costs; "
                "it does not manufacture benchmark evidence."
            ),
        }


def _transition_cost(
    transition_costs: Mapping[tuple[str, str], float],
    source: str,
    target: str,
) -> float:
    if source == target:
        return 0.0
    try:
        value = float(transition_costs[(source, target)])
    except KeyError as exc:
        raise ValueError(f"missing transition cost for {source!r} -> {target!r}") from exc
    if not math.isfinite(value) or value < 0:
        raise ValueError("transition costs must be finite and non-negative")
    return value


def _validate_inputs(
    phases: Sequence[AdaptationPhase],
    initial_candidate_id: str,
    transition_costs: Mapping[tuple[str, str], float],
) -> tuple[AdaptationPhase, ...]:
    if not initial_candidate_id.strip():
        raise ValueError("initial_candidate_id cannot be empty")
    items = tuple(phases)
    if not items:
        raise ValueError("at least one phase is required")
    for phase in items:
        phase.validate()
        if initial_candidate_id not in phase.per_query_cost:
            raise ValueError(f"initial candidate {initial_candidate_id!r} is missing from phase {phase.phase_id!r}")
    # Validate every declared transition eagerly so malformed negative/NaN data
    # cannot hide behind a policy path that happens not to use it.
    for (source, target), value in transition_costs.items():
        if not str(source).strip() or not str(target).strip():
            raise ValueError("transition candidate ids cannot be empty")
        numeric = float(value)
        if not math.isfinite(numeric) or numeric < 0:
            raise ValueError("transition costs must be finite and non-negative")
    return items


def _finish(policy: str, initial: str, steps: list[AdaptationStep]) -> AdaptationPolicyResult:
    execution = sum(step.execution_cost for step in steps)
    transition = sum(step.transition_cost for step in steps)
    return AdaptationPolicyResult(
        policy=policy,
        initial_candidate_id=initial,
        final_candidate_id=steps[-1].candidate_id,
        execution_cost=execution,
        transition_cost=transition,
        cumulative_cost=execution + transition,
        switches=sum(1 for step in steps if step.switched),
        steps=tuple(steps),
    )


def evaluate_never_switch(
    phases: Sequence[AdaptationPhase],
    *,
    initial_candidate_id: str,
    transition_costs: Mapping[tuple[str, str], float] | None = None,
) -> AdaptationPolicyResult:
    items = _validate_inputs(phases, initial_candidate_id, transition_costs or {})
    steps = [
        AdaptationStep(
            phase_id=phase.phase_id,
            candidate_id=initial_candidate_id,
            execution_cost=phase.queries * float(phase.per_query_cost[initial_candidate_id]),
            transition_cost=0.0,
            switched=False,
        )
        for phase in items
    ]
    return _finish("NEVER_SWITCH", initial_candidate_id, steps)


def evaluate_immediate_switch(
    phases: Sequence[AdaptationPhase],
    *,
    initial_candidate_id: str,
    transition_costs: Mapping[tuple[str, str], float],
) -> AdaptationPolicyResult:
    items = _validate_inputs(phases, initial_candidate_id, transition_costs)
    current = initial_candidate_id
    steps: list[AdaptationStep] = []
    for phase in items:
        target = min(phase.per_query_cost, key=lambda candidate: (float(phase.per_query_cost[candidate]), candidate))
        transition = _transition_cost(transition_costs, current, target)
        steps.append(
            AdaptationStep(
                phase_id=phase.phase_id,
                candidate_id=target,
                execution_cost=phase.queries * float(phase.per_query_cost[target]),
                transition_cost=transition,
                switched=target != current,
            )
        )
        current = target
    return _finish("IMMEDIATE_SWITCH", initial_candidate_id, steps)


def evaluate_transition_aware(
    phases: Sequence[AdaptationPhase],
    *,
    initial_candidate_id: str,
    transition_costs: Mapping[tuple[str, str], float],
    lambda_factor: float = 1.5,
    safety_margin_ratio: float = 0.10,
    cooldown_phases: int = 0,
) -> AdaptationPolicyResult:
    items = _validate_inputs(phases, initial_candidate_id, transition_costs)
    if not math.isfinite(lambda_factor) or lambda_factor < 0:
        raise ValueError("lambda_factor must be finite and non-negative")
    if not math.isfinite(safety_margin_ratio) or safety_margin_ratio < 0:
        raise ValueError("safety_margin_ratio must be finite and non-negative")
    if cooldown_phases < 0:
        raise ValueError("cooldown_phases cannot be negative")

    current = initial_candidate_id
    last_switch_index: int | None = None
    steps: list[AdaptationStep] = []
    for index, phase in enumerate(items):
        if current not in phase.per_query_cost:
            raise ValueError(f"current candidate {current!r} is missing from phase {phase.phase_id!r}")
        target = min(phase.per_query_cost, key=lambda candidate: (float(phase.per_query_cost[candidate]), candidate))
        current_phase_cost = phase.queries * float(phase.per_query_cost[current])
        target_phase_cost = phase.queries * float(phase.per_query_cost[target])
        transition = _transition_cost(transition_costs, current, target)
        benefit = max(0.0, current_phase_cost - target_phase_cost)
        threshold = lambda_factor * transition * (1.0 + safety_margin_ratio)
        cooldown_blocked = last_switch_index is not None and index <= last_switch_index + cooldown_phases
        should_switch = target != current and not cooldown_blocked and benefit > threshold

        selected = target if should_switch else current
        selected_transition = transition if should_switch else 0.0
        steps.append(
            AdaptationStep(
                phase_id=phase.phase_id,
                candidate_id=selected,
                execution_cost=phase.queries * float(phase.per_query_cost[selected]),
                transition_cost=selected_transition,
                switched=should_switch,
            )
        )
        if should_switch:
            current = selected
            last_switch_index = index
    return _finish("TRANSITION_AWARE", initial_candidate_id, steps)


def evaluate_offline_oracle(
    phases: Sequence[AdaptationPhase],
    *,
    initial_candidate_id: str,
    transition_costs: Mapping[tuple[str, str], float],
) -> AdaptationPolicyResult:
    """Exact dynamic-programming oracle for the finite caller-supplied phase set.

    This is an evaluation oracle, not a runtime policy: it uses future phases and
    therefore must never be presented as an online MORPHEUS controller.
    """

    items = _validate_inputs(phases, initial_candidate_id, transition_costs)
    candidate_sets = [tuple(sorted(phase.per_query_cost)) for phase in items]
    if any(not candidates for candidates in candidate_sets):  # defensive; validate already catches this
        raise ValueError("every phase requires candidates")

    costs: dict[str, float] = {}
    paths: dict[str, tuple[str, ...]] = {}
    first = items[0]
    for candidate in candidate_sets[0]:
        transition = _transition_cost(transition_costs, initial_candidate_id, candidate)
        costs[candidate] = transition + first.queries * float(first.per_query_cost[candidate])
        paths[candidate] = (candidate,)

    for phase_index in range(1, len(items)):
        phase = items[phase_index]
        next_costs: dict[str, float] = {}
        next_paths: dict[str, tuple[str, ...]] = {}
        for candidate in candidate_sets[phase_index]:
            execution = phase.queries * float(phase.per_query_cost[candidate])
            choices: list[tuple[float, tuple[str, ...], str]] = []
            for previous, prior_cost in costs.items():
                transition = _transition_cost(transition_costs, previous, candidate)
                path = paths[previous] + (candidate,)
                choices.append((prior_cost + transition + execution, path, previous))
            best_cost, best_path, _ = min(choices, key=lambda item: (item[0], item[1]))
            next_costs[candidate] = best_cost
            next_paths[candidate] = best_path
        costs, paths = next_costs, next_paths

    final_candidate = min(costs, key=lambda candidate: (costs[candidate], paths[candidate]))
    selected_path = paths[final_candidate]
    current = initial_candidate_id
    steps: list[AdaptationStep] = []
    for phase, candidate in zip(items, selected_path, strict=True):
        transition = _transition_cost(transition_costs, current, candidate)
        steps.append(
            AdaptationStep(
                phase_id=phase.phase_id,
                candidate_id=candidate,
                execution_cost=phase.queries * float(phase.per_query_cost[candidate]),
                transition_cost=transition,
                switched=candidate != current,
            )
        )
        current = candidate
    return _finish("OFFLINE_ORACLE", initial_candidate_id, steps)
