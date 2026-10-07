from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.security import SecurityPolicyMiddleware


def _app(*, api_key: str | None = None, limit: int = 0) -> FastAPI:
    app = FastAPI()
    app.add_middleware(SecurityPolicyMiddleware, api_key=api_key, rate_limit_per_minute=limit)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/private")
    def private() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/")
    def index() -> dict[str, str]:
        return {"page": "morpheus"}

    return app


def test_optional_api_key_guard_exempts_health_and_protects_other_api_routes() -> None:
    client = TestClient(_app(api_key="secret-key"))
    health = client.get("/api/health")
    denied = client.get("/api/private")
    allowed = client.get("/api/private", headers={"X-Morpheus-Key": "secret-key"})

    assert health.status_code == 200
    assert denied.status_code == 401
    assert allowed.status_code == 200
    for response in (health, denied, allowed):
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert denied.headers["cache-control"] == "no-store"
    assert allowed.headers["cache-control"] == "no-store"


def test_non_api_web_response_gets_browser_security_headers_without_api_cache_policy() -> None:
    response = TestClient(_app()).get("/")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert "cache-control" not in response.headers


def test_process_local_rate_limiter_rejects_request_after_window_budget() -> None:
    clock_value = [100.0]

    def clock() -> float:
        return clock_value[0]

    app = FastAPI()
    app.add_middleware(
        SecurityPolicyMiddleware,
        api_key=None,
        rate_limit_per_minute=2,
        clock=clock,
    )

    @app.get("/api/private")
    def private() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/api/private").status_code == 200
    assert client.get("/api/private").status_code == 200
    limited = client.get("/api/private")
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers

    clock_value[0] = 161.0
    assert client.get("/api/private").status_code == 200


def test_invalid_api_key_attempts_are_rate_limited_before_auth_rejection() -> None:
    clock_value = [100.0]

    def clock() -> float:
        return clock_value[0]

    app = FastAPI()
    app.add_middleware(
        SecurityPolicyMiddleware,
        api_key="correct-secret",
        rate_limit_per_minute=2,
        clock=clock,
    )

    @app.get("/api/private")
    def private() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    wrong = {"X-Morpheus-Key": "wrong-secret"}
    assert client.get("/api/private", headers=wrong).status_code == 401
    assert client.get("/api/private", headers=wrong).status_code == 401

    limited = client.get("/api/private", headers=wrong)
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers

    # Valid credentials use their own bounded identity and are not consumed by
    # the invalid-credential bucket.
    assert client.get(
        "/api/private",
        headers={"X-Morpheus-Key": "correct-secret"},
    ).status_code == 200

    clock_value[0] = 161.0
    assert client.get("/api/private", headers=wrong).status_code == 401
