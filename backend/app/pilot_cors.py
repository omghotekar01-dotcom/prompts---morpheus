from __future__ import annotations

import os
from urllib.parse import urlsplit

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response


_DEFAULT_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")
_ALLOWED_HEADERS = ("Content-Type", "X-Morpheus-Key", "X-Morpheus-Request-ID", "Idempotency-Key")
_ALLOWED_METHODS = ("POST", "OPTIONS")


def _canonical_origin(value: str) -> str:
    raw = value.strip()
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path not in {"", "/"}:
        raise ValueError(f"invalid pilot browser origin: {value!r}")
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError(f"invalid pilot browser origin: {value!r}")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError(f"invalid pilot browser origin: {value!r}")
    port = f":{parsed.port}" if parsed.port is not None else ""
    return f"{parsed.scheme.lower()}://{hostname.lower()}{port}"


def configured_pilot_origins(raw: str | None = None) -> tuple[str, ...]:
    if raw is None:
        raw = os.environ.get("MORPHEUS_PILOT_BROWSER_ORIGINS", "")
    candidates = [item.strip() for item in raw.split(",") if item.strip()] if raw.strip() else list(_DEFAULT_ORIGINS)
    origins = tuple(dict.fromkeys(_canonical_origin(item) for item in candidates))
    if not origins:
        raise ValueError("pilot browser origin policy cannot be empty")
    if any(origin == "*" for origin in origins):
        raise ValueError("wildcard pilot browser origins are forbidden")
    return origins


def _append_vary(response: Response, value: str) -> None:
    existing = response.headers.get("Vary", "")
    parts = [item.strip() for item in existing.split(",") if item.strip()]
    if value not in parts:
        parts.append(value)
    response.headers["Vary"] = ", ".join(parts)


class PilotCorsMiddleware(BaseHTTPMiddleware):
    """Strict CORS interoperability policy for `/api/v2/pilot/*` only.

    This middleware is not an authentication mechanism. The API-key middleware
    and deployment edge remain responsible for authorization/TLS policy.
    """

    def __init__(self, app, *, origins: tuple[str, ...] | None = None) -> None:
        super().__init__(app)
        self.origins = frozenset(origins if origins is not None else configured_pilot_origins())

    async def dispatch(self, request: Request, call_next) -> Response:
        if not request.url.path.startswith("/api/v2/pilot/"):
            return await call_next(request)

        origin = request.headers.get("Origin")
        if request.method == "OPTIONS" and request.headers.get("Access-Control-Request-Method"):
            if origin not in self.origins:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "pilot browser origin is not allowed"},
                    headers={"Cache-Control": "no-store", "Vary": "Origin"},
                )
            requested_method = request.headers.get("Access-Control-Request-Method", "").upper()
            requested_headers = {
                item.strip().lower()
                for item in request.headers.get("Access-Control-Request-Headers", "").split(",")
                if item.strip()
            }
            allowed_headers = {item.lower() for item in _ALLOWED_HEADERS}
            if requested_method != "POST" or not requested_headers <= allowed_headers:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "pilot browser preflight requested a method or header outside the explicit policy"},
                    headers={"Cache-Control": "no-store", "Vary": "Origin"},
                )
            return Response(
                status_code=204,
                headers={
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Methods": ", ".join(_ALLOWED_METHODS),
                    "Access-Control-Allow-Headers": ", ".join(_ALLOWED_HEADERS),
                    "Access-Control-Max-Age": "600",
                    "Cache-Control": "no-store",
                    "Vary": "Origin",
                },
            )

        response = await call_next(request)
        if origin in self.origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            _append_vary(response, "Origin")
        return response
