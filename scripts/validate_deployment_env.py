#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit


SCHEMA = "morpheus-deployment-environment-preflight-v1"
_DEFAULT_AI_TIMEOUT_SECONDS = 20.0
_ALLOWED_AI_PROVIDERS = {"disabled", "ollama", "openai_compatible"}


def _unquote(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        return stripped[1:-1]
    return stripped


def _load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        raise ValueError("environment file does not exist")
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError(f"invalid environment assignment at line {line_number}")
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if (
            not key
            or not (key[0].isalpha() or key[0] == "_")
            or not all(ch.isalnum() or ch == "_" for ch in key)
        ):
            raise ValueError(f"invalid environment variable name at line {line_number}")
        values[key] = _unquote(raw_value)
    return values


def _check(check_id: str, passed: bool, detail: str) -> dict[str, object]:
    return {"id": check_id, "passed": bool(passed), "detail": detail}


def _canonical_origin(value: str) -> str:
    raw = value.strip()
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path not in {"", "/"}:
        raise ValueError("invalid browser origin")
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError("invalid browser origin")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("invalid browser origin")
    try:
        parsed_port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid browser origin") from exc
    port = f":{parsed_port}" if parsed_port is not None else ""
    return f"{parsed.scheme.lower()}://{hostname.lower()}{port}"


def _browser_origins_are_valid(raw: str) -> bool:
    if not raw.strip():
        return True
    try:
        origins = tuple(
            dict.fromkeys(
                _canonical_origin(item)
                for item in raw.split(",")
                if item.strip()
            )
        )
    except (ValueError, TypeError):
        return False
    return bool(origins) and "*" not in origins


def _public_domain_is_valid(domain: str) -> bool:
    if not domain or any(ch.isspace() for ch in domain):
        return False
    parsed = urlsplit(f"//{domain}")
    try:
        parsed_port = parsed.port
    except ValueError:
        return False
    return bool(
        parsed.hostname
        and parsed.hostname.lower() == domain.lower()
        and "." in domain
        and parsed_port is None
        and not parsed.path
        and not parsed.query
        and not parsed.fragment
        and parsed.username is None
        and parsed.password is None
    )


def _container_writable_override(value: str) -> bool:
    if not value:
        return True
    normalized = value.replace("\\", "/")
    return (
        normalized == "/data"
        or normalized.startswith("/data/")
        or normalized == "/tmp"
        or normalized.startswith("/tmp/")
    )


def _ai_configuration(values: dict[str, str]) -> tuple[bool, bool]:
    aliases = {
        "": "disabled",
        "off": "disabled",
        "none": "disabled",
        "disabled": "disabled",
        "ollama": "ollama",
        "openai": "openai_compatible",
        "openai_compatible": "openai_compatible",
    }
    raw_provider = values.get("MORPHEUS_AI_PROVIDER", "disabled").strip().lower().replace("-", "_")
    provider = aliases.get(raw_provider)
    if provider not in _ALLOWED_AI_PROVIDERS:
        return False, True
    if provider == "disabled":
        try:
            timeout = float(values.get("MORPHEUS_AI_TIMEOUT_SECONDS", str(_DEFAULT_AI_TIMEOUT_SECONDS)) or _DEFAULT_AI_TIMEOUT_SECONDS)
        except ValueError:
            return False, False
        return 1.0 <= timeout <= 120.0, False

    model = values.get("MORPHEUS_AI_MODEL", "").strip()
    raw_base = values.get("MORPHEUS_AI_BASE_URL", "").strip()
    if provider == "ollama" and not raw_base:
        raw_base = "http://127.0.0.1:11434"
    if not model or not raw_base or len(raw_base) > 2048:
        return False, True

    parsed = urlsplit(raw_base)
    base_ok = bool(
        parsed.scheme in {"http", "https"}
        and parsed.netloc
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
    )
    try:
        timeout = float(values.get("MORPHEUS_AI_TIMEOUT_SECONDS", str(_DEFAULT_AI_TIMEOUT_SECONDS)) or _DEFAULT_AI_TIMEOUT_SECONDS)
    except ValueError:
        timeout = 0.0
    return base_ok and 1.0 <= timeout <= 120.0, True


def validate_environment(values: dict[str, str], *, public: bool) -> dict[str, object]:
    checks: list[dict[str, object]] = []

    api_key = values.get("MORPHEUS_API_KEY", "")
    checks.append(
        _check(
            "api_key",
            len(api_key) >= 24,
            (
                "Control-plane key meets the guarded-pilot minimum length."
                if len(api_key) >= 24
                else "Set a fresh control-plane key of at least 24 characters."
            ),
        )
    )

    raw_limit = values.get("MORPHEUS_RATE_LIMIT_PER_MINUTE", "").strip()
    try:
        rate_limit = int(raw_limit)
    except ValueError:
        rate_limit = 0
    checks.append(
        _check(
            "rate_limit",
            rate_limit > 0,
            (
                f"Process-local rate limit configured at {rate_limit} requests/minute."
                if rate_limit > 0
                else "Set MORPHEUS_RATE_LIMIT_PER_MINUTE to a positive integer."
            ),
        )
    )

    if public:
        domain = values.get("MORPHEUS_DOMAIN", "").strip()
        domain_ok = _public_domain_is_valid(domain)
        checks.append(
            _check(
                "public_domain",
                domain_ok,
                (
                    "Public HTTPS domain is structurally configured."
                    if domain_ok
                    else "Set MORPHEUS_DOMAIN to one bare DNS hostname before public launch."
                ),
            )
        )

    browser_origins = values.get("MORPHEUS_PILOT_BROWSER_ORIGINS", "").strip()
    if browser_origins:
        origins_ok = _browser_origins_are_valid(browser_origins)
        checks.append(
            _check(
                "browser_origins",
                origins_ok,
                (
                    "Explicit split-origin browser policy is valid."
                    if origins_ok
                    else "MORPHEUS_PILOT_BROWSER_ORIGINS is malformed or unsafe."
                ),
            )
        )

    ai_ok, ai_enabled = _ai_configuration(values)
    checks.append(
        _check(
            "ai_provider",
            ai_ok,
            (
                "Optional AI configuration is structurally valid."
                if ai_ok and ai_enabled
                else "AI is disabled; deterministic MORPHEUS remains fully available."
                if ai_ok
                else "Optional AI configuration is invalid; fix it or disable the provider."
            ),
        )
    )

    for variable in (
        "MORPHEUS_STATE_DIR",
        "MORPHEUS_DB_PATH",
        "MORPHEUS_ARTIFACT_DIR",
        "MORPHEUS_IDEMPOTENCY_DB_PATH",
    ):
        value = values.get(variable, "").strip()
        if not value:
            continue
        safe = True if not public else _container_writable_override(value)
        checks.append(
            _check(
                f"path_override:{variable}",
                safe,
                (
                    "Advanced path override remains within a writable deployment mount."
                    if safe
                    else "For the hardened public container, keep writable path overrides under /data or /tmp."
                ),
            )
        )

    blockers = [str(item["id"]) for item in checks if item["passed"] is not True]
    return {
        "schema": SCHEMA,
        "mode": "PUBLIC_HTTPS_GUARDED_PILOT" if public else "LOCAL_PRIVATE_GUARDED_PILOT",
        "ready": not blockers,
        "checks": checks,
        "blockers": blockers,
        "secrets_echoed": False,
        "production_deployment_authorized": False,
        "truth_boundary": (
            "This static preflight validates deployment configuration shape only. "
            "It does not test DNS, TLS issuance, filesystem permissions, native compilation, "
            "runtime readiness, security certification, scientific claims or production reliability."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate MORPHEUS guarded-pilot deployment configuration without printing secrets."
    )
    parser.add_argument("--env-file", default=".env")
    parser.add_argument(
        "--public",
        action="store_true",
        help="Require public HTTPS domain configuration and container-safe path overrides.",
    )
    args = parser.parse_args()

    try:
        file_values = _load_dotenv(Path(args.env_file))
    except (OSError, UnicodeError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "ready": False,
                    "blockers": ["env_file"],
                    "error": str(exc),
                    "secrets_echoed": False,
                    "production_deployment_authorized": False,
                },
                sort_keys=True,
            )
        )
        return 2

    # Process-level MORPHEUS_* variables take precedence over file values so
    # Docker/CI/secret-manager injection can safely override tracked placeholders.
    values = dict(file_values)
    values.update(
        {
            key: value
            for key, value in os.environ.items()
            if key.startswith("MORPHEUS_")
        }
    )
    report = validate_environment(values, public=args.public)
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report["ready"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
