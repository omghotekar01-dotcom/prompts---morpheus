from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Iterable

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class PilotRetryExecutionLeaseConsumption:
    schema: str
    operation: str
    key_sha256: str
    request_sha256: str
    lease_sha256: str
    consumer_sha256: str
    lease_sequence: int
    consumed_at_utc: str
    execution_permitted: bool
    manual_resolution_required: bool
    consumption_sha256: str

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
    if parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") != value:
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


def consume_retry_execution_lease(
    lease: Any,
    *,
    consumer_sha256: str,
    consumed_at: datetime,
    prior_consumptions: Iterable[Any] = (),
) -> PilotRetryExecutionLeaseConsumption:
    if getattr(lease, "schema", None) != "morpheus-pilot-retry-fresh-authorization-lease-v1":
        raise ValueError("unsupported retry execution lease schema")
    if getattr(lease, "execution_permitted", None) is not True:
        raise ValueError("lease does not permit execution")
    if getattr(lease, "manual_resolution_required", None) is not False:
        raise ValueError("manual resolution state cannot be consumed")

    operation = getattr(lease, "operation", None)
    if not isinstance(operation, str) or not operation.strip() or operation != operation.strip():
        raise ValueError("operation must be canonical non-empty text")
    lease_sequence = getattr(lease, "lease_sequence", None)
    if not isinstance(lease_sequence, int) or isinstance(lease_sequence, bool) or lease_sequence < 1:
        raise ValueError("lease_sequence must be an integer >= 1")

    key = _sha("key_sha256", getattr(lease, "key_sha256", None))
    request = _sha("request_sha256", getattr(lease, "request_sha256", None))
    lease_id = _sha("lease_sha256", getattr(lease, "lease_sha256", None))
    consumer = _sha("consumer_sha256", consumer_sha256)
    if len({key, request, lease_id, consumer}) != 4:
        raise ValueError("consumption evidence identities must be independent")

    leased_at = _parse_utc("leased_at_utc", getattr(lease, "leased_at_utc", None))
    expires_at = _parse_utc("expires_at_utc", getattr(lease, "expires_at_utc", None))
    consumed, consumed_text = _utc("consumed_at", consumed_at)
    if expires_at < leased_at:
        raise ValueError("lease expiry precedes lease issuance")
    if consumed < leased_at:
        raise ValueError("lease consumption cannot precede lease issuance")
    if consumed > expires_at:
        raise ValueError("retry execution lease expired before consumption")

    seen = set()
    for item in prior_consumptions:
        prior_lease = _sha("prior lease_sha256", getattr(item, "lease_sha256", None))
        if prior_lease in seen:
            raise ValueError("duplicate prior lease consumption evidence")
        seen.add(prior_lease)
    if lease_id in seen:
        raise ValueError("retry execution lease has already been consumed")

    payload = {
        "schema": "morpheus-pilot-retry-execution-lease-consumption-v1",
        "operation": operation,
        "key_sha256": key,
        "request_sha256": request,
        "lease_sha256": lease_id,
        "consumer_sha256": consumer,
        "lease_sequence": lease_sequence,
        "consumed_at_utc": consumed_text,
        "execution_permitted": True,
        "manual_resolution_required": False,
    }
    return PilotRetryExecutionLeaseConsumption(**payload, consumption_sha256=_digest(payload))
