from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class PilotRetryFreshAuthorizationLease:
    schema: str
    operation: str
    key_sha256: str
    request_sha256: str
    authorization_sha256: str
    lease_policy_sha256: str
    leased_at_utc: str
    expires_at_utc: str
    lease_sequence: int
    execution_permitted: bool
    manual_resolution_required: bool
    lease_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha(name: str, value: Any) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _parse_utc(name: str, value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{name} must be canonical UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{name} must be canonical UTC") from exc
    canonical = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if canonical != value:
        raise ValueError(f"{name} must be canonical UTC")
    return parsed


def _utc(name: str, value: datetime) -> tuple[datetime, str]:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    parsed = value.astimezone(timezone.utc)
    return parsed, parsed.isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def issue_retry_execution_lease(
    authorization: Any,
    *,
    lease_policy_sha256: str,
    lease_sequence: int,
    leased_at: datetime,
) -> PilotRetryFreshAuthorizationLease:
    if getattr(authorization, "schema", None) != "morpheus-pilot-retry-ledger-fresh-authorization-v1":
        raise ValueError("unsupported retry authorization schema")
    if getattr(authorization, "retry_authorized", None) is not True:
        raise ValueError("authorization does not permit retry")
    if getattr(authorization, "manual_resolution_required", None) is not False:
        raise ValueError("manual resolution state cannot receive an execution lease")
    if not isinstance(lease_sequence, int) or isinstance(lease_sequence, bool) or lease_sequence < 1:
        raise ValueError("lease_sequence must be an integer >= 1")

    operation = getattr(authorization, "operation", None)
    if not isinstance(operation, str) or not operation.strip() or operation != operation.strip():
        raise ValueError("operation must be canonical non-empty text")

    key = _sha("key_sha256", getattr(authorization, "key_sha256", None))
    request = _sha("request_sha256", getattr(authorization, "request_sha256", None))
    authorization_id = _sha("authorization_sha256", getattr(authorization, "authorization_sha256", None))
    policy = _sha("lease_policy_sha256", lease_policy_sha256)
    if len({key, request, authorization_id, policy}) != 4:
        raise ValueError("lease evidence identities must be independent")

    authorized_at = _parse_utc("authorized_at_utc", getattr(authorization, "authorized_at_utc", None))
    expires_at = _parse_utc("authorization_expires_at_utc", getattr(authorization, "authorization_expires_at_utc", None))
    leased, leased_text = _utc("leased_at", leased_at)
    if expires_at < authorized_at:
        raise ValueError("authorization expiry precedes authorization time")
    if leased < authorized_at:
        raise ValueError("lease cannot precede authorization")
    if leased > expires_at:
        raise ValueError("retry authorization expired before lease issuance")

    payload = {
        "schema": "morpheus-pilot-retry-fresh-authorization-lease-v1",
        "operation": operation,
        "key_sha256": key,
        "request_sha256": request,
        "authorization_sha256": authorization_id,
        "lease_policy_sha256": policy,
        "leased_at_utc": leased_text,
        "expires_at_utc": expires_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "lease_sequence": lease_sequence,
        "execution_permitted": True,
        "manual_resolution_required": False,
    }
    return PilotRetryFreshAuthorizationLease(**payload, lease_sha256=_digest(payload))
