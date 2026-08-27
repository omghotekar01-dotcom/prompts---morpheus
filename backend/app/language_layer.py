from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from .copilot import CopilotResponse, answer_from_run


ALLOWED_INTENTS = frozenset(
    {
        "winner_explanation",
        "measurement_evidence",
        "pareto_tradeoffs",
        "correctness_verification",
        "constraint_rejections",
        "runtime_adaptation",
        "general_summary",
    }
)


class LanguageProvider(Protocol):
    """Optional text-to-JSON provider contract.

    Providers are translators only. They are never handed credentials, shell
    tools, benchmark authority, database mutation capability, or a direct route
    to change MORPHEUS state through this protocol.
    """

    def complete_json(self, prompt: str) -> str: ...


@dataclass(frozen=True)
class LanguagePlan:
    intent: str
    normalized_question: str
    provider_mode: str
    provider_raw_sha256: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "normalized_question": self.normalized_question,
            "provider_mode": self.provider_mode,
            "provider_raw_sha256": self.provider_raw_sha256,
            "evidence_state": "LANGUAGE_TRANSLATION_ONLY_NO_STATE_AUTHORITY",
        }


def _deterministic_intent(question: str) -> str:
    query = question.lower()
    if any(token in query for token in ("why", "choose", "selected", "winner")):
        return "winner_explanation"
    if any(token in query for token in ("measure", "benchmark", "speed", "evidence", "confidence")):
        return "measurement_evidence"
    if any(token in query for token in ("pareto", "alternative", "tradeoff", "trade-off")):
        return "pareto_tradeoffs"
    if any(token in query for token in ("correct", "verify", "safe", "compile")):
        return "correctness_verification"
    if any(token in query for token in ("constraint", "memory", "limit", "rejected")):
        return "constraint_rejections"
    if any(token in query for token in ("runtime", "adapt", "drift", "switch", "rollback")):
        return "runtime_adaptation"
    return "general_summary"


def plan_question(question: str, provider: LanguageProvider | None = None) -> LanguagePlan:
    normalized = " ".join(question.strip().split())
    if not normalized:
        raise ValueError("question cannot be empty")
    if len(normalized) > 4000:
        raise ValueError("question exceeds 4000 characters")

    if provider is None:
        return LanguagePlan(
            intent=_deterministic_intent(normalized),
            normalized_question=normalized,
            provider_mode="DETERMINISTIC_LOCAL",
        )

    prompt = json.dumps(
        {
            "task": "Classify the user question for MORPHEUS evidence Copilot. Return JSON only.",
            "allowed_intents": sorted(ALLOWED_INTENTS),
            "question": normalized,
            "output_schema": {"intent": "one allowed_intent", "normalized_question": "string"},
            "rules": [
                "Do not answer the engineering question.",
                "Do not request tools, commands, credentials, files, URLs, code execution, or state changes.",
                "Do not invent evidence.",
            ],
        },
        sort_keys=True,
    )
    raw = provider.complete_json(prompt)
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 32_000:
        raise ValueError("language provider response must be a bounded JSON string")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("language provider returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("language provider response must be a JSON object")
    extra = set(parsed) - {"intent", "normalized_question"}
    if extra:
        raise ValueError(f"language provider returned forbidden fields: {sorted(extra)}")
    intent = str(parsed.get("intent", ""))
    if intent not in ALLOWED_INTENTS:
        raise ValueError("language provider returned an unsupported intent")
    provider_question = " ".join(str(parsed.get("normalized_question", normalized)).strip().split())
    if not provider_question or len(provider_question) > 4000:
        raise ValueError("language provider returned an invalid normalized question")

    import hashlib

    return LanguagePlan(
        intent=intent,
        normalized_question=provider_question,
        provider_mode="OPTIONAL_TOOL_RESTRICTED_PROVIDER",
        provider_raw_sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
    )


def answer_with_language_layer(
    run: dict[str, Any],
    question: str,
    provider: LanguageProvider | None = None,
) -> dict[str, Any]:
    """Translate language, then delegate all evidence claims to deterministic Copilot."""

    plan = plan_question(question, provider)
    response: CopilotResponse = answer_from_run(run, plan.normalized_question)
    payload = response.as_dict()
    payload["language_plan"] = plan.as_dict()
    payload["mode"] = (
        "TOOL_RESTRICTED_LANGUAGE_PLUS_DETERMINISTIC_EVIDENCE"
        if provider is not None
        else response.mode
    )
    payload.setdefault("limitations", []).append(
        "Any optional language provider can translate wording only; deterministic persisted-run evidence remains authoritative."
    )
    return payload
