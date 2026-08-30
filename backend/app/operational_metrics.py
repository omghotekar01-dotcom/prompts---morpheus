from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from threading import RLock
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA256_SEGMENT_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_UUID_SEGMENT_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_INTEGER_SEGMENT_RE = re.compile(r"^[0-9]{1,20}$")


def normalize_metric_path(path: str) -> str:
    """Bound path cardinality without inspecting request bodies, queries or headers."""

    segments: list[str] = []
    for segment in path.split("/"):
        if not segment:
            continue
        if _SHA256_SEGMENT_RE.fullmatch(segment):
            segments.append(":sha256")
        elif _UUID_SEGMENT_RE.fullmatch(segment):
            segments.append(":uuid")
        elif _INTEGER_SEGMENT_RE.fullmatch(segment):
            segments.append(":int")
        elif len(segment) > 80:
            segments.append(":opaque")
        else:
            segments.append(segment)
    return "/" + "/".join(segments)


def canonical_request_id(raw: str | None) -> str:
    candidate = (raw or "").strip()
    if candidate and _REQUEST_ID_RE.fullmatch(candidate):
        return candidate
    return uuid.uuid4().hex


@dataclass
class _RouteAggregate:
    requests: int = 0
    errors_4xx: int = 0
    errors_5xx: int = 0
    duration_ms_total: float = 0.0
    duration_ms_max: float = 0.0

    def record(self, status_code: int, duration_ms: float) -> None:
        self.requests += 1
        if 400 <= status_code < 500:
            self.errors_4xx += 1
        elif status_code >= 500:
            self.errors_5xx += 1
        self.duration_ms_total += duration_ms
        self.duration_ms_max = max(self.duration_ms_max, duration_ms)

    def as_dict(self, *, method: str, path: str) -> dict[str, object]:
        mean = self.duration_ms_total / self.requests if self.requests else 0.0
        return {
            "method": method,
            "path": path,
            "requests": self.requests,
            "errors_4xx": self.errors_4xx,
            "errors_5xx": self.errors_5xx,
            "duration_ms_mean": round(mean, 3),
            "duration_ms_max": round(self.duration_ms_max, 3),
        }


class OperationalMetrics:
    """Small process-local telemetry registry for pilot operations.

    It intentionally avoids labels derived from request bodies, API keys, query
    strings or arbitrary high-cardinality identifiers. It is not a distributed
    metrics backend and is reset on process restart.
    """

    def __init__(self, *, clock: Callable[[], float] = time.monotonic, max_route_keys: int = 64) -> None:
        self._clock = clock
        self._started = clock()
        self._max_route_keys = max(1, max_route_keys)
        self._lock = RLock()
        self._in_flight = 0
        self._requests_total = 0
        self._status_classes = {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0}
        self._routes: dict[tuple[str, str], _RouteAggregate] = {}
        self._overflow_route_observations = 0

    def begin(self) -> None:
        with self._lock:
            self._in_flight += 1

    def finish(self, *, method: str, path: str, status_code: int, duration_ms: float) -> None:
        normalized_method = method.upper()[:16]
        normalized_path = normalize_metric_path(path)
        with self._lock:
            self._in_flight = max(0, self._in_flight - 1)
            self._requests_total += 1
            status_bucket = f"{status_code // 100}xx"
            if status_bucket in self._status_classes:
                self._status_classes[status_bucket] += 1

            key = (normalized_method, normalized_path)
            if key not in self._routes:
                overflow_key = (normalized_method, "/:other")
                # Reserve the final slot for one overflow aggregate. For a limit
                # of one, every route is intentionally folded into that bucket.
                regular_capacity = max(0, self._max_route_keys - 1)
                if len(self._routes) >= regular_capacity:
                    key = overflow_key
                    self._overflow_route_observations += 1
            aggregate = self._routes.setdefault(key, _RouteAggregate())
            aggregate.record(status_code, max(0.0, duration_ms))

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            routes = [
                aggregate.as_dict(method=method, path=path)
                for (method, path), aggregate in sorted(self._routes.items())
            ]
            uptime = max(0.0, self._clock() - self._started)
            return {
                "schema": "morpheus-operational-metrics-v1",
                "evidence_state": "PROCESS_LOCAL_OPERATIONAL_TELEMETRY",
                "uptime_seconds": round(uptime, 3),
                "requests_total": self._requests_total,
                "in_flight": self._in_flight,
                "status_classes": dict(self._status_classes),
                "route_key_count": len(self._routes),
                "route_key_limit": self._max_route_keys,
                "overflow_route_observations": self._overflow_route_observations,
                "routes": routes,
                "truth_boundaries": [
                    "Metrics are process-local and reset on restart; they are not an HA telemetry backend or SLA record.",
                    "Route labels are normalized and bounded; request bodies, query strings, API keys and authorization material are never recorded.",
                    "Latency is wall-clock middleware duration and includes application/middleware work in this process only.",
                ],
            }


class RequestObservabilityMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        metrics: OperationalMetrics | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(app)
        self.metrics = metrics if metrics is not None else METRICS
        self.clock = clock

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = canonical_request_id(request.headers.get("X-Morpheus-Request-ID"))
        started = self.clock()
        self.metrics.begin()
        status_code = 500
        response: Response | None = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            elapsed_ms = max(0.0, (self.clock() - started) * 1000.0)
            self.metrics.finish(
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                duration_ms=elapsed_ms,
            )
            if response is not None:
                response.headers.setdefault("X-Morpheus-Request-ID", request_id)
                response.headers.setdefault("Server-Timing", f"morpheus;dur={elapsed_ms:.3f}")


METRICS = OperationalMetrics()
