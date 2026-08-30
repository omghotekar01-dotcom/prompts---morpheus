from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class PilotRetryLedgerFreshAuthorization:
    schema: str
    operation: str
    key_sha256: str
    request_sha256: str
    verification_sha256: str
    freshness_sha256: str
    authorization_policy_sha256: str
    authorized_at_utc: str
    authorization_expires_at_utc: str
    retry_authorized: bool
    manual_resolution_required: bool
    authorization_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha(name: str, value: Any) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _utc(name: str, value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def authorize_retry_from_fresh_verification(
    freshness: Any,
    *,
    authorization_policy_sha256: str,
    authorized_at: datetime,
) -> PilotRetryLedgerFreshAuthorization:
    if getattr(freshness, "schema", None) != "morpheus-pilot-retry-ledger-verification-freshness-v1":
        raise ValueError("unsupported freshness evidence schema")
    if getattr(freshness, "retry_permitted", None) is not True:
        raise ValueError("freshness evidence does not permit retry")
    if getattr(freshness, "fresh", None) is not True:
        raise ValueError("retry authorization requires fresh verification evidence")
    if getattr(freshness, "manual_resolution_required", None) is not False:
        raise ValueError("manual resolution state cannot be retry-authorized")
    if getattr(freshness, "disposition", None) != "RETRY_PENDING":
        raise ValueError("retry authorization requires RETRY_PENDING disposition")

    operation = getattr(freshness, "operation", None)
    if not isinstance(operation, str) or not operation.strip() or operation != operation.strip():
        raise ValueError("operation must be canonical non-empty text")

    key = _sha("key_sha256", getattr(freshness, "key_sha256", None))
    request = _sha("request_sha256", getattr(freshness, "request_sha256", None))
    verification = _sha("verification_sha256", getattr(freshness, "verification_sha256", None))
    freshness_id = _sha("freshness_sha256", getattr(freshness, "freshness_sha256", None))
    policy = _sha("authorization_policy_sha256", authorization_policy_sha256)
    if len({key, request, verification, freshness_id, policy}) != 5:
        raise ValueError("retry authorization evidence identities must be independent")

    evaluated_at = _parse_utc("evaluated_at_utc", getattr(freshness, "evaluated_at_utc", None))
    verified_at = _parse_utc("verified_at_utc", getattr(freshness, "verified_at_utc", None))
    max_age = getattr(freshness, "max_age_seconds", None)
    if not isinstance(max_age, int) or isinstance(max_age, bool) or max_age < 1:
        raise ValueError("max_age_seconds must be an integer >= 1")
    if evaluated_at < verified_at:
        raise ValueError("freshness evidence time ordering is invalid")

    authorized_text = _utc("authorized_at", authorized_at)
    authorized = datetime.fromisoformat(authorized_text[:-1] + "+00:00")
    if authorized < evaluated_at:
        raise ValueError("authorization cannot precede freshness evaluation")

    expires = verified_at.timestamp() + max_age
    if authorized.timestamp() > expires:
        raise ValueError("freshness evidence expired before authorization")
    expires_text = datetime.fromtimestamp(expires, tz=timezone.utc).isoformat().replace("+00:00", "Z")

    payload = {
        "schema": "morpheus-pilot-retry-ledger-fresh-authorization-v1",
        "operation": operation,
        "key_sha256": key,
        "request_sha256": request,
        "verification_sha256": verification,
        "freshness_sha256": freshness_id,
        "authorization_policy_sha256": policy,
        "authorized_at_utc": authorized_text,
        "authorization_expires_at_utc": expires_text,
        "retry_authorized": True,
        "manual_resolution_required": False,
    }
    return PilotRetryLedgerFreshAuthorization(**payload, authorization_sha256=_digest(payload))
