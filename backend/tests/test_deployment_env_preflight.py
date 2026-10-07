from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "validate_deployment_env.py"


def _run(tmp_path: Path, text: str, *extra: str) -> subprocess.CompletedProcess[str]:
    env_file = tmp_path / ".env"
    env_file.write_text(text, encoding="utf-8")
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("MORPHEUS_")
    }
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--env-file", str(env_file), *extra],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )


def test_public_deployment_environment_can_pass_without_echoing_secret(tmp_path: Path) -> None:
    secret = "very-secret-pilot-control-key-123456"
    process = _run(
        tmp_path,
        "\n".join(
            [
                f"MORPHEUS_API_KEY={secret}",
                "MORPHEUS_RATE_LIMIT_PER_MINUTE=120",
                "MORPHEUS_DOMAIN=pilot.example.com",
                "MORPHEUS_AI_PROVIDER=disabled",
            ]
        ),
        "--public",
    )

    assert process.returncode == 0, process.stdout + process.stderr
    payload = json.loads(process.stdout)
    assert payload["ready"] is True
    assert payload["blockers"] == []
    assert payload["secrets_echoed"] is False
    assert payload["production_deployment_authorized"] is False
    assert secret not in process.stdout
    assert secret not in process.stderr


def test_short_control_plane_key_blocks_public_preflight_without_echoing_value(tmp_path: Path) -> None:
    secret = "too-short"
    process = _run(
        tmp_path,
        "\n".join(
            [
                f"MORPHEUS_API_KEY={secret}",
                "MORPHEUS_RATE_LIMIT_PER_MINUTE=120",
                "MORPHEUS_DOMAIN=pilot.example.com",
                "MORPHEUS_AI_PROVIDER=disabled",
            ]
        ),
        "--public",
    )

    assert process.returncode == 3
    payload = json.loads(process.stdout)
    assert "api_key" in payload["blockers"]
    assert secret not in process.stdout


def test_public_preflight_rejects_read_only_root_path_override(tmp_path: Path) -> None:
    process = _run(
        tmp_path,
        "\n".join(
            [
                "MORPHEUS_API_KEY=pilot-control-key-long-enough-123",
                "MORPHEUS_RATE_LIMIT_PER_MINUTE=120",
                "MORPHEUS_DOMAIN=pilot.example.com",
                "MORPHEUS_AI_PROVIDER=disabled",
                "MORPHEUS_ARTIFACT_DIR=/opt/morpheus/runtime-artifacts",
            ]
        ),
        "--public",
    )

    assert process.returncode == 3
    payload = json.loads(process.stdout)
    assert "path_override:MORPHEUS_ARTIFACT_DIR" in payload["blockers"]


def test_invalid_optional_ai_configuration_blocks_preflight(tmp_path: Path) -> None:
    process = _run(
        tmp_path,
        "\n".join(
            [
                "MORPHEUS_API_KEY=pilot-control-key-long-enough-123",
                "MORPHEUS_RATE_LIMIT_PER_MINUTE=120",
                "MORPHEUS_DOMAIN=pilot.example.com",
                "MORPHEUS_AI_PROVIDER=openai_compatible",
                "MORPHEUS_AI_MODEL=test-model",
                "MORPHEUS_AI_BASE_URL=not-a-url",
            ]
        ),
        "--public",
    )

    assert process.returncode == 3
    payload = json.loads(process.stdout)
    assert "ai_provider" in payload["blockers"]


def test_deployment_preflight_has_no_backend_or_third_party_runtime_imports() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "from app." not in source
    assert "import fastapi" not in source
    assert "import httpx" not in source
    assert "import pydantic" not in source


def test_public_preflight_rejects_malformed_domain_port_without_traceback(tmp_path: Path) -> None:
    process = _run(
        tmp_path,
        "\n".join(
            [
                "MORPHEUS_API_KEY=pilot-control-key-long-enough-123",
                "MORPHEUS_RATE_LIMIT_PER_MINUTE=120",
                "MORPHEUS_DOMAIN=pilot.example.com:notaport",
                "MORPHEUS_AI_PROVIDER=disabled",
            ]
        ),
        "--public",
    )

    assert process.returncode == 3
    payload = json.loads(process.stdout)
    assert "public_domain" in payload["blockers"]
    assert "Traceback" not in process.stderr
