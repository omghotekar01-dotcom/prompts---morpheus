from __future__ import annotations

from subprocess import CompletedProcess

import pytest

from app import java_plan_scorer as bridge
from app.models import CandidateResult, FieldSpec, QueryKind, QuerySpec, WorkloadSpec


def workload(*, memory_mb: float | None = 0.05, update_rate: float = 0.0) -> WorkloadSpec:
    return WorkloadSpec.model_validate({
        "record_count": 1739, "fields": [{"name": "arbitrary_x", "type": "string", "cardinality": 77}],
        "queries": [{"kind": "point_lookup", "field": "arbitrary_x", "weight": 1}],
        "constraints": {"memory_mb": memory_mb, "update_rate": update_rate},
        "objective": {"latency": 1, "memory": 0.15, "update": 0.20, "build": 0.05},
    })


def candidate(*, latency: float = 0.2, memory: float = 0.04) -> CandidateResult:
    return CandidateResult(
        id="test-metrics", assignments=[], unique_primitives=["robin_hood_hash"],
        predicted_latency_us=latency, predicted_memory_mb=memory,
        predicted_build_ms=1.2, predicted_update_us=0.17,
        score=999, feasible=True, rejection_reasons=[],
    )


def test_explicit_java_is_fail_closed_when_no_runtime(monkeypatch):
    monkeypatch.setenv("MORPHEUS_PLAN_SCORER", "java")
    monkeypatch.setattr(bridge, "java_plan_scorer_command", lambda: None)
    with pytest.raises(bridge.JavaPlanScorerError, match="required"):
        bridge.apply_java_plan_scores(workload(), [candidate()])


def test_explicit_python_is_retainable_migration_path(monkeypatch):
    monkeypatch.setenv("MORPHEUS_PLAN_SCORER", "python")
    monkeypatch.setattr(bridge, "java_plan_scorer_command", lambda: None)
    assert bridge.apply_java_plan_scores(workload(), [candidate()]) is None


def test_java_protocol_drives_feasibility_and_scoring(monkeypatch):
    monkeypatch.setenv("MORPHEUS_PLAN_SCORER", "java")
    monkeypatch.setattr(bridge, "java_plan_scorer_command",
                        lambda: ["java", "-cp", "test-classes", "com.morpheus.dsa.PlanScorer"])
    observed = []

    def fake_run(command, **kwargs):
        observed.append(kwargs["input"])
        assert kwargs["timeout"] == 20 and kwargs["check"] is False
        return CompletedProcess(command, 0, "OK 2\nR 1.234 0\nR 2.5 1\n", "")

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    scored = bridge.apply_java_plan_scores(workload(), [
        candidate(memory=0.04), candidate(memory=0.10),
    ])
    assert scored is not None
    assert scored[0].score == 1.234 and scored[0].feasible
    assert scored[1].score == 2.5 and not scored[1].feasible
    assert "memory" in scored[1].rejection_reasons[0]
    assert observed[0].startswith("MORPHEUS_JAVA_SCORE_V1\n2\n")
    assert "arbitrary_x" not in observed[0]  # Cost/constraint data only, no preset schema.


@pytest.mark.parametrize("response", [
    "", "OK 1\nR 0.1 0\n", "OK 2\nR nan 0\nR 1 0\n",
    "OK 2\nR 0.1 8\nR 1 0\n", "OK 2\nR nope 0\nR 1 0\n",
])
def test_invalid_java_protocol_does_not_silently_fall_back(monkeypatch, response):
    monkeypatch.setenv("MORPHEUS_PLAN_SCORER", "java")
    monkeypatch.setattr(bridge, "java_plan_scorer_command", lambda: ["java"])
    monkeypatch.setattr(bridge.subprocess, "run",
                        lambda *args, **kwargs: CompletedProcess(args[0], 0, response, ""))
    with pytest.raises(bridge.JavaPlanScorerError):
        bridge.apply_java_plan_scores(workload(), [candidate(), candidate()])


def test_live_java_scoring_for_different_memory_budgets(monkeypatch):
    monkeypatch.setenv("MORPHEUS_PLAN_SCORER", "java")
    if bridge.java_plan_scorer_command() is None:
        pytest.skip("compile Java core and set MORPHEUS_JAVA_CLASSES to verify real runtime")
    strict = bridge.apply_java_plan_scores(workload(memory_mb=0.05), [candidate(memory=0.09)])
    broad = bridge.apply_java_plan_scores(workload(memory_mb=0.50), [candidate(memory=0.09)])
    assert strict is not None and broad is not None
    assert not strict[0].feasible and broad[0].feasible
    assert strict[0].score != broad[0].score
