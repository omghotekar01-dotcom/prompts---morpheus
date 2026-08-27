from __future__ import annotations

import hmac
import os
import time
from collections import defaultdict, deque
from threading import RLock
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response


class SecurityPolicyMiddleware(BaseHTTPMiddleware):
    """Optional local-control-plane API key guard and bounded request limiter.

    The policy is disabled by default so local development remains frictionless.
    Set `MORPHEUS_API_KEY` to require `X-Morpheus-Key` on `/api/*` except health.
    Set `MORPHEUS_RATE_LIMIT_PER_MINUTE` to a positive integer to enable the
    process-local sliding-window limiter. This is defense-in-depth for the MVP,
    not a substitute for an API gateway or distributed production rate limiter.
    """

    def __init__(
        self,
        app,
        *,
        api_key: str | None = None,
        rate_limit_per_minute: int | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(app)
        self.api_key = api_key if api_key is not None else os.environ.get("MORPHEUS_API_KEY")
        configured_limit = rate_limit_per_minute
        if configured_limit is None:
            raw = os.environ.get("MORPHEUS_RATE_LIMIT_PER_MINUTE", "0").strip()
            try:
                configured_limit = int(raw or "0")
            except ValueError:
                configured_limit = 0
        self.rate_limit_per_minute = max(0, configured_limit)
        self.clock = clock
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = RLock()

    async def dispatch(self, request: Request, call_next) -> Response:
        if not request.url.path.startswith("/api/") or request.url.path == "/api/health":
            return await call_next(request)

        if self.api_key:
            supplied = request.headers.get("X-Morpheus-Key", "")
            if not hmac.compare_digest(supplied, self.api_key):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "MORPHEUS API key required"},
                    headers={"Cache-Control": "no-store"},
                )

        if self.rate_limit_per_minute > 0:
            identity = self._identity(request)
            now = self.clock()
            window_start = now - 60.0
            with self._lock:
                history = self._requests[identity]
                while history and history[0] <= window_start:
                    history.popleft()
                if len(history) >= self.rate_limit_per_minute:
                    retry_after = max(1, int(60.0 - (now - history[0]))) if history else 60
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "MORPHEUS process-local rate limit exceeded"},
                        headers={"Retry-After": str(retry_after), "Cache-Control": "no-store"},
                    )
                history.append(now)

        response = await call_next(request)
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    def _identity(self, request: Request) -> str:
        supplied = request.headers.get("X-Morpheus-Key")
        if supplied:
            return f"key:{hmac.new(b'morpheus-rate-limit', supplied.encode('utf-8'), 'sha256').hexdigest()}"
        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"
