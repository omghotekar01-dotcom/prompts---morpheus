from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.pilot_cors import configured_pilot_origins
from app.server import app


client = TestClient(app)


def test_pilot_origin_parser_rejects_paths_credentials_and_non_http_schemes() -> None:
    assert configured_pilot_origins("https://pilot.example.com,http://localhost:5173") == (
        "https://pilot.example.com",
        "http://localhost:5173",
    )
    for raw in (
        "*",
        "file:///tmp/ui",
        "https://pilot.example.com/path",
        "https://user:password@pilot.example.com",
    ):
        with pytest.raises(ValueError, match="invalid pilot browser origin|wildcard"):
            configured_pilot_origins(raw)


def test_allowed_pilot_preflight_exposes_only_explicit_method_and_headers() -> None:
    response = client.options(
        "/api/v2/pilot/synthesize",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,idempotency-key,x-morpheus-request-id,x-morpheus-key",
        },
    )
    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-methods"] == "POST, OPTIONS"
    allowed = response.headers["access-control-allow-headers"].lower()
    assert "idempotency-key" in allowed
    assert "x-morpheus-request-id" in allowed
    assert "x-morpheus-key" in allowed
    assert "*" not in response.headers["access-control-allow-origin"]
    assert "access-control-allow-credentials" not in response.headers


def test_disallowed_origin_and_unlisted_header_fail_preflight_closed() -> None:
    bad_origin = client.options(
        "/api/v2/pilot/synthesize",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,idempotency-key",
        },
    )
    assert bad_origin.status_code == 403
    assert "access-control-allow-origin" not in bad_origin.headers

    bad_header = client.options(
        "/api/v2/pilot/synthesize",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,idempotency-key,x-unsafe-debug-token",
        },
    )
    assert bad_header.status_code == 403


def test_actual_pilot_response_echoes_only_allowed_origin() -> None:
    missing_key = client.post(
        "/api/v2/pilot/synthesize",
        headers={"Origin": "http://localhost:5173"},
        json={"spec_text": "invalid"},
    )
    assert missing_key.status_code == 422
    assert missing_key.headers["access-control-allow-origin"] == "http://localhost:5173"

    disallowed = client.post(
        "/api/v2/pilot/synthesize",
        headers={"Origin": "https://evil.example"},
        json={"spec_text": "invalid"},
    )
    assert disallowed.status_code == 422
    assert "access-control-allow-origin" not in disallowed.headers
