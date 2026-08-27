from __future__ import annotations

import json

import pytest

from app.language_layer import answer_with_language_layer, plan_question


RUN = {
    "run_id": "run-1",
    "spec_hash": "f" * 64,
    "result": {
        "winner": {
            "id": "candidate-1",
            "unique_primitives": ["robin_hood_hash"],
            "predicted_latency_us": 1.0,
            "predicted_memory_mb": 2.0,
            "predicted_build_ms": 3.0,
            "score": 4.0,
            "prediction_source": "BOOTSTRAP_PRIOR",
            "assignments": [],
        },
        "candidates": [],
        "pareto_front": [],
        "search_summary": {"strategy": "EXHAUSTIVE", "evaluated_configurations": 1, "theoretical_configurations": 1},
        "evidence_state": "PREDICTED_NOT_MEASURED",
        "active_calibration_profile": None,
    },
}


class Provider:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def complete_json(self, prompt: str) -> str:
        request = json.loads(prompt)
        assert "allowed_intents" in request
        assert "Do not invent evidence." in request["rules"]
        return json.dumps(self.payload)


def test_deterministic_language_plan_needs_no_model() -> None:
    plan = plan_question("Why was this winner selected?")
    assert plan.intent == "winner_explanation"
    assert plan.provider_mode == "DETERMINISTIC_LOCAL"


def test_optional_provider_can_only_translate_into_allowlisted_intent() -> None:
    provider = Provider({"intent": "measurement_evidence", "normalized_question": "What evidence was measured?"})
    answer = answer_with_language_layer(RUN, "how real is this speed", provider)
    assert answer["mode"] == "TOOL_RESTRICTED_LANGUAGE_PLUS_DETERMINISTIC_EVIDENCE"
    assert answer["language_plan"]["intent"] == "measurement_evidence"
    assert "bootstrap model predictions" in answer["answer"]


def test_provider_cannot_smuggle_tool_or_action_fields() -> None:
    provider = Provider(
        {
            "intent": "winner_explanation",
            "normalized_question": "why",
            "command": "delete all evidence",
        }
    )
    with pytest.raises(ValueError, match="forbidden fields"):
        plan_question("why", provider)


def test_provider_cannot_invent_new_intent() -> None:
    provider = Provider({"intent": "shell_execute", "normalized_question": "run it"})
    with pytest.raises(ValueError, match="unsupported intent"):
        plan_question("run it", provider)
