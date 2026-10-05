from __future__ import annotations

import json

import httpx
import pytest

from app.ai_provider import (
    AIProviderConfig,
    AIProviderError,
    ConfiguredAIProvider,
    ai_provider_status,
    configured_ai_provider,
    load_ai_provider_config,
)


def test_ai_provider_is_disabled_by_default() -> None:
    config = load_ai_provider_config({})
    assert config.provider == "disabled"
    assert config.configured is False
    assert configured_ai_provider(env={}) is None
    assert ai_provider_status({})["mode"] == "DETERMINISTIC_ONLY"


def test_ollama_defaults_to_loopback_and_never_claims_authority() -> None:
    config = load_ai_provider_config(
        {
            "MORPHEUS_AI_PROVIDER": "ollama",
            "MORPHEUS_AI_MODEL": "local-model",
        }
    )
    assert config.base_url == "http://127.0.0.1:11434"
    status = ConfiguredAIProvider(config).public_status()
    assert status["evidence_authority"] is False
    assert status["automatic_control_authority"] is False


def test_openai_compatible_provider_requires_explicit_base_url() -> None:
    with pytest.raises(AIProviderError, match="BASE_URL"):
        load_ai_provider_config(
            {
                "MORPHEUS_AI_PROVIDER": "openai_compatible",
                "MORPHEUS_AI_MODEL": "example-model",
            }
        )


def test_provider_rejects_embedded_url_credentials() -> None:
    with pytest.raises(AIProviderError, match="must not embed credentials"):
        load_ai_provider_config(
            {
                "MORPHEUS_AI_PROVIDER": "openai_compatible",
                "MORPHEUS_AI_MODEL": "example-model",
                "MORPHEUS_AI_BASE_URL": "https://user:secret@example.invalid/v1",
            }
        )


def test_ollama_chat_shape_and_bounded_json_translation() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("authorization")
        payload = json.loads(request.content)
        seen["payload"] = payload
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": '{"intent":"winner_explanation","normalized_question":"why"}',
                }
            },
        )

    config = AIProviderConfig(
        provider="ollama",
        base_url="http://127.0.0.1:11434",
        model="local-model",
        api_key=None,
        timeout_seconds=5.0,
    )
    provider = ConfiguredAIProvider(config, transport=httpx.MockTransport(handler))
    output = provider.complete_json('{"question":"why"}')

    assert json.loads(output)["intent"] == "winner_explanation"
    assert seen["url"] == "http://127.0.0.1:11434/api/chat"
    assert seen["authorization"] is None
    assert seen["payload"]["stream"] is False
    assert seen["payload"]["model"] == "local-model"


def test_openai_compatible_chat_uses_server_side_bearer_key() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "validated text"}}]},
        )

    config = AIProviderConfig(
        provider="openai_compatible",
        base_url="https://example.invalid/v1",
        model="example-model",
        api_key="server-secret",
        timeout_seconds=5.0,
    )
    provider = ConfiguredAIProvider(config, transport=httpx.MockTransport(handler))
    assert provider.complete_text([{"role": "user", "content": "hello"}]) == "validated text"
    assert seen["url"] == "https://example.invalid/v1/chat/completions"
    assert seen["authorization"] == "Bearer server-secret"


def test_provider_failure_does_not_leak_remote_response_body() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="REMOTE SECRET ERROR DETAIL")

    provider = ConfiguredAIProvider(
        AIProviderConfig(
            provider="ollama",
            base_url="http://127.0.0.1:11434",
            model="local-model",
            api_key=None,
            timeout_seconds=5.0,
        ),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(AIProviderError) as exc_info:
        provider.complete_text([{"role": "user", "content": "hello"}])
    assert "REMOTE SECRET" not in str(exc_info.value)
