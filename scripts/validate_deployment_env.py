#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai_provider import AIProviderError, load_ai_provider_config  # noqa: E402
from app.pilot_cors import configured_pilot_origins  # noqa: E402


SCHEMA = "morpheus-deployment-environment-preflight-v1"


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


def _public_domain_is_valid(domain: str) -> bool:
    if not domain or any(ch.isspace() for ch in domain):
        return False
    parsed = urlsplit(f"//{domain}")
    return bool(
        parsed.hostname
        and parsed.hostname.lower() == domain.lower()
        and "." in domain
        and parsed.port is None
        and not parsed.path
        and not parsed.query
        and not parsed.fragment
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
        checks.append(
            _check(
                "public_domain",
                _public_domain_is_valid(domain),
                (
                    "Public HTTPS domain is structurally configured."
                    if _public_domain_is_valid(domain)
                    else "Set MORPHEUS_DOMAIN to one bare DNS hostname before public launch."
                ),
            )
        )

    browser_origins = values.get("MORPHEUS_PILOT_BROWSER_ORIGINS", "").strip()
    if browser_origins:
        try:
            configured_pilot_origins(browser_origins)
        except ValueError:
            origins_ok = False
        else:
            origins_ok = True
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

    try:
        ai_config = load_ai_provider_config(values)
    except AIProviderError:
        ai_ok = False
        ai_enabled = True
    else:
        ai_ok = True
        ai_enabled = ai_config.configured
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

    values = dict(os.environ)
    values.update(file_values)
    report = validate_environment(values, public=args.public)
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report["ready"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
