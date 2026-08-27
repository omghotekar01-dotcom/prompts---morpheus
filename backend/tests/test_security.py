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

    return app


def test_optional_api_key_guard_exempts_health_and_protects_other_api_routes() -> None:
    client = TestClient(_app(api_key="secret-key"))
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/private").status_code == 401
    allowed = client.get("/api/private", headers={"X-Morpheus-Key": "secret-key"})
    assert allowed.status_code == 200
    assert allowed.headers["cache-control"] == "no-store"
    assert allowed.headers["x-content-type-options"] == "nosniff"


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
