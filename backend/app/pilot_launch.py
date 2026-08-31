from __future__ import annotations

import hashlib
import ipaddress
import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class PilotLaunchPlan:
    schema: str
    host: str
    port: int
    workers: int
    loopback_only: bool
    explicit_network_bind: bool
    production_deployment_authorized: bool
    evidence_state: str
    truth_boundaries: tuple[str, ...]
    sha256: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["truth_boundaries"] = list(self.truth_boundaries)
        return payload


def _canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _is_loopback(host: str) -> bool:
    lowered = host.lower()
    if lowered == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def build_pilot_launch_plan(
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    allow_network_bind: bool = False,
) -> PilotLaunchPlan:
    """Validate the declared single-process pilot serving boundary.

    The launcher intentionally fixes the worker count at one because rate-limit
    counters and operational metrics are process-local and the current deployment
    contract is a single-node engineering pilot, not a multi-worker production
    topology.
    """

    if not isinstance(host, str) or host != host.strip() or not host or len(host) > 255:
        raise ValueError("pilot host must be a canonical non-empty host string")
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise ValueError("pilot port must be an integer from 1 through 65535")

    loopback = _is_loopback(host)
    if not loopback and not allow_network_bind:
        raise ValueError("non-loopback pilot bind requires explicit --allow-network-bind acknowledgement")

    boundaries = (
        "The launcher always uses one worker; process-local telemetry and rate limiting are not aggregated across workers.",
        "A non-loopback bind does not provide TLS, external identity, a gateway/WAF, tenancy or production network hardening; those controls must be supplied outside MORPHEUS.",
        "Passing startup preflight permits only the declared single-node engineering pilot and does not authorize external production deployment.",
    )
    core = {
        "schema": "morpheus-pilot-launch-plan-v1",
        "host": host,
        "port": port,
        "workers": 1,
        "loopback_only": loopback,
        "explicit_network_bind": bool(allow_network_bind and not loopback),
        "production_deployment_authorized": False,
        "evidence_state": "VALIDATED_SINGLE_NODE_PILOT_LAUNCH_PLAN",
        "truth_boundaries": list(boundaries),
    }
    return PilotLaunchPlan(
        schema=core["schema"],
        host=host,
        port=port,
        workers=1,
        loopback_only=loopback,
        explicit_network_bind=bool(allow_network_bind and not loopback),
        production_deployment_authorized=False,
        evidence_state=core["evidence_state"],
        truth_boundaries=boundaries,
        sha256=_canonical_sha256(core),
    )
