from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlparse

import httpx


class AIProviderError(RuntimeError):
    """Bounded provider failure safe to surface without response-body leakage."""


@dataclass(frozen=True)
class AIProviderConfig:
    provider: str
    base_url: str | None
    model: str | None
    api_key: str | None
    timeout_seconds: float

    @property
    def configured(self) -> bool:
        return self.provider != "disabled" and bool(self.base_url) and bool(self.model)

    def public_dict(self) -> dict[str, object]:
        return {
            "configured": self.configured,
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "api_key_configured": bool(self.api_key),
            "timeout_seconds": self.timeout_seconds,
            "evidence_authority": False,
            "automatic_control_authority": False,
        }


def _bounded_timeout(raw: str | None) -> float:
    if raw is None or not raw.strip():
        return 20.0
    try:
        value = float(raw)
    except ValueError as exc:
        raise AIProviderError("MORPHEUS_AI_TIMEOUT_SECONDS must be numeric") from exc
    if not 1.0 <= value <= 120.0:
        raise AIProviderError("MORPHEUS_AI_TIMEOUT_SECONDS must be between 1 and 120")
    return value


def _normalize_base_url(provider: str, raw: str | None) -> str | None:
    if provider == "disabled":
        return None
    value = (raw or ("http://127.0.0.1:11434" if provider == "ollama" else "")).strip().rstrip("/")
    if not value:
        raise AIProviderError("MORPHEUS_AI_BASE_URL is required for the selected AI provider")
    if len(value) > 2048:
        raise AIProviderError("MORPHEUS_AI_BASE_URL is too long")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise AIProviderError("MORPHEUS_AI_BASE_URL must be an http(s) URL")
    if parsed.username or parsed.password:
        raise AIProviderError("MORPHEUS_AI_BASE_URL must not embed credentials")
    if parsed.query or parsed.fragment:
        raise AIProviderError("MORPHEUS_AI_BASE_URL must not contain query or fragment components")
    return value


def load_ai_provider_config(env: dict[str, str] | None = None) -> AIProviderConfig:
    source = os.environ if env is None else env
    raw_provider = source.get("MORPHEUS_AI_PROVIDER", "disabled").strip().lower().replace("-", "_")
    aliases = {
        "": "disabled",
        "off": "disabled",
        "none": "disabled",
        "disabled": "disabled",
        "ollama": "ollama",
        "openai": "openai_compatible",
        "openai_compatible": "openai_compatible",
    }
    if raw_provider not in aliases:
        raise AIProviderError("MORPHEUS_AI_PROVIDER must be disabled, ollama, or openai_compatible")
    provider = aliases[raw_provider]
    model = source.get("MORPHEUS_AI_MODEL", "").strip() or None
    if provider != "disabled" and not model:
        raise AIProviderError("MORPHEUS_AI_MODEL is required when AI is enabled")
    return AIProviderConfig(
        provider=provider,
        base_url=_normalize_base_url(provider, source.get("MORPHEUS_AI_BASE_URL")),
        model=model,
        api_key=source.get("MORPHEUS_AI_API_KEY", "").strip() or None,
        timeout_seconds=_bounded_timeout(source.get("MORPHEUS_AI_TIMEOUT_SECONDS")),
    )


def _strip_code_fence(text: str) -> str:
    value = text.strip()
    fences = ("~~~", chr(96) * 3)
    if any(value.startswith(fence) and value.endswith(fence) for fence in fences):
        lines = value.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return value


class ConfiguredAIProvider:
    """Minimal outbound text provider with no tool/state authority."""

    def __init__(self, config: AIProviderConfig, *, transport: httpx.BaseTransport | None = None) -> None:
        if not config.configured:
            raise AIProviderError("AI provider is not configured")
        self.config = config
        self._transport = transport

    def public_status(self) -> dict[str, object]:
        return {
            **self.config.public_dict(),
            "mode": "OPTIONAL_LANGUAGE_PROVIDER_NO_EVIDENCE_AUTHORITY",
        }

    def _endpoint(self) -> str:
        assert self.config.base_url is not None
        if self.config.provider == "ollama":
            return f"{self.config.base_url}/api/chat"
        if self.config.provider == "openai_compatible":
            base = self.config.base_url.rstrip("/")
            return f"{base}/chat/completions" if base.endswith("/v1") else f"{base}/v1/chat/completions"
        raise AIProviderError("unsupported AI provider")

    def complete_text(
        self,
        messages: Iterable[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 1200,
    ) -> str:
        payload_messages = list(messages)
        if not payload_messages or len(payload_messages) > 16:
            raise AIProviderError("AI request must contain between 1 and 16 messages")
        if max_tokens < 1 or max_tokens > 4096:
            raise AIProviderError("AI max_tokens is outside the allowed range")
        if temperature < 0 or temperature > 1:
            raise AIProviderError("AI temperature is outside the allowed range")

        headers = {"User-Agent": "MORPHEUS/0.10"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        if self.config.provider == "ollama":
            payload: dict[str, Any] = {
                "model": self.config.model,
                "messages": payload_messages,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            }
        else:
            payload = {
                "model": self.config.model,
                "messages": payload_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

        try:
            with httpx.Client(
                timeout=self.config.timeout_seconds,
                transport=self._transport,
                follow_redirects=False,
            ) as client:
                response = client.post(self._endpoint(), headers=headers, json=payload)
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AIProviderError("configured AI provider request failed") from exc

        try:
            if self.config.provider == "ollama":
                text_value = str(body["message"]["content"])
            else:
                text_value = str(body["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError("configured AI provider returned an unsupported response shape") from exc

        text_value = text_value.strip()
        if not text_value:
            raise AIProviderError("configured AI provider returned an empty response")
        if len(text_value.encode("utf-8")) > 64_000:
            raise AIProviderError("configured AI provider response exceeded 64 KB")
        return text_value

    def complete_json(self, prompt: str) -> str:
        raw = self.complete_text(
            [
                {
                    "role": "system",
                    "content": "Return only one valid JSON object. Do not use markdown or code fences.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=600,
        )
        candidate = _strip_code_fence(raw)
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise AIProviderError("configured AI provider returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise AIProviderError("configured AI provider JSON response must be an object")
        return json.dumps(parsed, separators=(",", ":"), ensure_ascii=True)


def configured_ai_provider(
    *,
    env: dict[str, str] | None = None,
    transport: httpx.BaseTransport | None = None,
) -> ConfiguredAIProvider | None:
    config = load_ai_provider_config(env)
    if not config.configured:
        return None
    return ConfiguredAIProvider(config, transport=transport)


def ai_provider_status(env: dict[str, str] | None = None) -> dict[str, object]:
    try:
        config = load_ai_provider_config(env)
    except AIProviderError as exc:
        return {
            "configured": False,
            "provider": "invalid_configuration",
            "model": None,
            "base_url": None,
            "api_key_configured": False,
            "evidence_authority": False,
            "automatic_control_authority": False,
            "configuration_error": str(exc),
        }
    return {
        **config.public_dict(),
        "configuration_error": None,
        "mode": (
            "OPTIONAL_LANGUAGE_PROVIDER_NO_EVIDENCE_AUTHORITY"
            if config.configured
            else "DETERMINISTIC_ONLY"
        ),
    }
