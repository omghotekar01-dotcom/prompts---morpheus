from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .ai_provider import AIProviderError, ai_provider_status, configured_ai_provider
from .parser import SpecParseError, parse_workload_document


router = APIRouter(prefix="/api/v2/ai", tags=["MORPHEUS optional AI language layer"])


class AIWorkloadDraftRequest(BaseModel):
    description: str = Field(min_length=8, max_length=8000)
    base_spec_text: str | None = Field(default=None, max_length=64_000)


def _provider_or_503():
    try:
        provider = configured_ai_provider()
    except AIProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if provider is None:
        raise HTTPException(
            status_code=503,
            detail="optional AI provider is disabled; configure MORPHEUS_AI_PROVIDER and MORPHEUS_AI_MODEL",
        )
    return provider


def _decode_json_object(raw: str) -> dict[str, Any]:
    candidate = raw.strip()
    fence = chr(96) * 3
    if candidate.startswith(fence) and candidate.endswith(fence):
        lines = candidate.splitlines()
        if len(lines) >= 3:
            candidate = "\n".join(lines[1:-1]).strip()
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise AIProviderError("AI provider returned invalid JSON for workload drafting") from exc
    if not isinstance(parsed, dict):
        raise AIProviderError("AI workload draft response must be a JSON object")
    return parsed


def _extract_draft_payload(payload: dict[str, Any]) -> tuple[str, list[str]]:
    allowed = {"mws_yaml", "assumptions"}
    extra = set(payload) - allowed
    if extra:
        raise AIProviderError(f"AI workload draft returned forbidden fields: {sorted(extra)}")
    mws_yaml = payload.get("mws_yaml")
    assumptions = payload.get("assumptions", [])
    if not isinstance(mws_yaml, str) or not mws_yaml.strip():
        raise AIProviderError("AI workload draft is missing mws_yaml")
    if len(mws_yaml.encode("utf-8")) > 256_000:
        raise AIProviderError("AI workload draft exceeds the MWS size limit")
    if not isinstance(assumptions, list) or len(assumptions) > 32:
        raise AIProviderError("AI workload draft assumptions must be a bounded list")
    normalized_assumptions: list[str] = []
    for item in assumptions:
        value = str(item).strip()
        if not value or len(value) > 500:
            raise AIProviderError("AI workload draft contains an invalid assumption")
        normalized_assumptions.append(value)
    return mws_yaml.strip() + "\n", normalized_assumptions


def _draft_prompt(description: str, base_spec_text: str | None) -> str:
    schema_rules = {
        "version": "mws-0.1",
        "top_level_keys": ["version", "name", "record_count", "fields", "queries", "constraints", "objective"],
        "field": {"name": "identifier", "type": "short string", "cardinality": "optional positive integer"},
        "query_kinds": [
            "point_lookup",
            "range_scan",
            "filter",
            "prefix_search",
            "graph_traversal",
            "insert",
            "update",
            "delete",
        ],
        "query_keys": [
            "kind",
            "field",
            "weight",
            "selectivity",
            "result_limit",
            "prefix_length",
            "distribution",
        ],
        "distribution_kinds": ["uniform", "sequential", "hotspot", "zipf"],
        "constraints": ["memory_mb", "p99_latency_us", "update_rate", "build_time_ms"],
        "objective": ["latency", "memory", "update", "build"],
    }
    request: dict[str, Any] = {
        "task": "Draft a MORPHEUS Workload Specification (MWS) for explicit user review.",
        "user_description": description,
        "schema_rules": schema_rules,
        "output_schema": {
            "mws_yaml": "one complete YAML document as a JSON string",
            "assumptions": ["short assumption strings for values not explicitly supplied by the user"],
        },
        "rules": [
            "Return JSON only with exactly mws_yaml and assumptions.",
            "Do not synthesize a data structure or choose a MORPHEUS candidate.",
            "Do not claim measurements, benchmark results, production readiness, novelty, or deployment authority.",
            "Use only documented MWS keys; no comments or prose inside mws_yaml.",
            "If a quantity is unknown, choose a reviewable engineering default and disclose it in assumptions.",
            "Weights must be positive and referenced fields must exist.",
        ],
    }
    if base_spec_text:
        request["base_spec_text"] = base_spec_text
        request["edit_rule"] = "Preserve existing semantics unless the user description explicitly asks to change them."
    return json.dumps(request, sort_keys=True, ensure_ascii=True)


def _repair_prompt(
    description: str,
    invalid_payload: dict[str, Any],
    error: str,
) -> str:
    return json.dumps(
        {
            "task": "Repair an invalid MORPHEUS MWS draft. Return JSON only.",
            "user_description": description,
            "invalid_output": invalid_payload,
            "validation_error": error[:8000],
            "output_schema": {
                "mws_yaml": "one complete corrected YAML document as a JSON string",
                "assumptions": ["short assumption strings"],
            },
            "rules": [
                "Return exactly mws_yaml and assumptions.",
                "Fix only what is needed for valid mws-0.1 semantics.",
                "Do not add benchmark, deployment, novelty, or automatic-control claims.",
            ],
        },
        sort_keys=True,
        ensure_ascii=True,
    )


@router.get("/status")
def ai_status() -> dict[str, object]:
    return {
        "schema": "morpheus-ai-provider-status-v1",
        **ai_provider_status(),
        "truth_boundary": (
            "AI is optional language/drafting assistance only. Deterministic MWS validation, persisted evidence, "
            "measurement gates and control policy remain authoritative."
        ),
    }


@router.post("/test")
def ai_test() -> dict[str, object]:
    provider = _provider_or_503()
    prompt = json.dumps(
        {
            "task": "Return exactly the requested JSON object.",
            "output": {"status": "ok"},
            "rules": ["No extra fields.", "JSON only."],
        },
        sort_keys=True,
    )
    try:
        raw = provider.complete_json(prompt)
        parsed = json.loads(raw)
    except (AIProviderError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="configured AI provider did not pass the bounded JSON probe") from exc
    if parsed != {"status": "ok"}:
        raise HTTPException(status_code=502, detail="configured AI provider returned the wrong probe payload")
    return {
        "reachable": True,
        "provider": provider.public_status(),
        "truth_boundary": "Connectivity/model-format probe only; no evidence or production capability is inferred.",
    }


@router.post("/workload-draft")
def ai_workload_draft(request: AIWorkloadDraftRequest) -> dict[str, object]:
    provider = _provider_or_503()
    if request.base_spec_text is not None:
        try:
            parse_workload_document(request.base_spec_text)
        except SpecParseError as exc:
            raise HTTPException(status_code=422, detail=f"base_spec_text is invalid: {exc}") from exc

    prompt = _draft_prompt(request.description, request.base_spec_text)
    attempts = 0
    last_error: str | None = None
    parsed_payload: dict[str, Any] | None = None

    for attempt in range(2):
        attempts = attempt + 1
        try:
            raw = provider.complete_text(
                [
                    {
                        "role": "system",
                        "content": (
                            "You draft MORPHEUS mws-0.1 YAML for human review. "
                            "Return one JSON object only and never claim measurements or control authority."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1 if attempt == 0 else 0.0,
                max_tokens=1800,
            )
            parsed_payload = _decode_json_object(raw)
            draft_text, provider_assumptions = _extract_draft_payload(parsed_payload)
            document = parse_workload_document(draft_text)
            return {
                "schema": "morpheus-ai-workload-draft-v1",
                "validated": True,
                "attempts": attempts,
                "draft_spec_text": draft_text,
                "resolved_semantic_hash": document.resolved_semantic_hash,
                "provider_assumptions": provider_assumptions,
                "resolution_assumptions": list(document.assumptions),
                "provider": provider.public_status(),
                "evidence_state": "AI_DRAFT_VALIDATED_MWS_USER_REVIEW_REQUIRED",
                "eligible_for_runtime_automatic_control": False,
                "truth_boundary": (
                    "The AI output becomes usable only because the deterministic MWS parser accepted the returned draft. "
                    "The user must review/apply it; this endpoint does not synthesize, benchmark, persist, migrate, deploy, or authorize runtime control."
                ),
            }
        except AIProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except SpecParseError as exc:
            last_error = str(exc)
            if attempt == 0 and parsed_payload is not None:
                prompt = _repair_prompt(request.description, parsed_payload, last_error)
                continue
            break

    raise HTTPException(
        status_code=422,
        detail=f"AI provider could not produce a valid MWS after {attempts} bounded attempts: {last_error or 'unknown validation error'}",
    )
