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
    Set `MORPHEUS_API_KEY` to require `X-Morpheus-Key` on `/api/*` except
    health. Set `MORPHEUS_RATE_LIMIT_PER_MINUTE` to a positive integer to
    enable the process-local sliding-window limiter.

    Invalid credential attempts are rate-limited by the directly observed peer
    address before returning 401. MORPHEUS deliberately does not trust
    Forwarded/X-Forwarded-* headers in this process-local boundary.

    This is defense-in-depth for the guarded single-node pilot, not a substitute
    for an API gateway, distributed limiter, tenant identity system or WAF.
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
        is_api = request.url.path.startswith("/api/")
        protected_api = (
            is_api
            and request.method != "OPTIONS"
            and request.url.path != "/api/health"
        )

        supplied = request.headers.get("X-Morpheus-Key", "")
        credential_valid = (
            not self.api_key
            or hmac.compare_digest(supplied, self.api_key)
        )

        # Consume a budget before returning an authentication failure. Otherwise
        # an attacker could make unlimited invalid-key guesses because the old
        # early 401 return bypassed the limiter entirely.
        if protected_api and self.rate_limit_per_minute > 0:
            identity = (
                self._identity(request)
                if credential_valid
                else self._auth_failure_identity(request)
            )
            limited = self._consume_rate_limit(identity)
            if limited is not None:
                return self._apply_security_headers(limited, is_api=True)

        if protected_api and self.api_key and not credential_valid:
            return self._apply_security_headers(
                JSONResponse(
                    status_code=401,
                    content={"detail": "MORPHEUS API key required"},
                ),
                is_api=True,
            )

        response = await call_next(request)
        return self._apply_security_headers(response, is_api=is_api)

    def _consume_rate_limit(self, identity: str) -> JSONResponse | None:
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
                    headers={"Retry-After": str(retry_after)},
                )
            history.append(now)
        return None

    @staticmethod
    def _apply_security_headers(response: Response, *, is_api: bool) -> Response:
        """Apply conservative browser-facing headers without claiming a hardened edge.

        CSP is compatible with the packaged Vite application: scripts/assets are
        same-origin and React style attributes require the explicitly declared
        inline-style allowance. HSTS is intentionally omitted because local
        development and pilot operation may use plain HTTP behind an external
        TLS terminator.
        """

        if is_api:
            response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "font-src 'self' data:; "
                "connect-src 'self'; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "frame-ancestors 'none'"
            ),
        )
        return response

    def _identity(self, request: Request) -> str:
        supplied = request.headers.get("X-Morpheus-Key")
        if supplied:
            return f"key:{hmac.new(b'morpheus-rate-limit', supplied.encode('utf-8'), 'sha256').hexdigest()}"
        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"

    @staticmethod
    def _auth_failure_identity(request: Request) -> str:
        # Never hash or otherwise retain the attacker-supplied candidate secret:
        # all invalid credentials from the same directly observed peer share one
        # bounded failure bucket.
        client_host = request.client.host if request.client else "unknown"
        return f"auth-failure-ip:{client_host}"
