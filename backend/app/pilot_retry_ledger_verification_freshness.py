from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class PilotRetryLedgerVerificationFreshness:
    schema: str
    operation: str
    key_sha256: str
    request_sha256: str
    verification_sha256: str
    disposition: str
    verified_at_utc: str
    evaluated_at_utc: str
    max_age_seconds: int
    fresh: bool
    retry_permitted: bool
    manual_resolution_required: bool
    freshness_sha256: str

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


def _utc(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("evaluated_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def evaluate_retry_ledger_verification_freshness(
    verification: Any,
    *,
    evaluated_at: datetime,
    max_age_seconds: int,
) -> PilotRetryLedgerVerificationFreshness:
    if getattr(verification, "schema", None) != "morpheus-pilot-retry-ledger-seal-verification-v1":
        raise ValueError("unsupported retry ledger verification schema")
    if getattr(verification, "verified", None) is not True:
        raise ValueError("retry ledger verification must be positively verified")
    if not isinstance(max_age_seconds, int) or isinstance(max_age_seconds, bool) or max_age_seconds < 1:
        raise ValueError("max_age_seconds must be an integer >= 1")

    operation = getattr(verification, "operation", None)
    if not isinstance(operation, str) or not operation.strip() or operation != operation.strip():
        raise ValueError("operation must be canonical non-empty text")
    key = _sha("key_sha256", getattr(verification, "key_sha256", None))
    request = _sha("request_sha256", getattr(verification, "request_sha256", None))
    verification_id = _sha("verification_sha256", getattr(verification, "verification_sha256", None))
    if len({key, request, verification_id}) != 3:
        raise ValueError("freshness evidence identities must be independent")

    disposition = getattr(verification, "disposition", None)
    if disposition not in {"COMPLETED", "MANUAL_RESOLUTION", "RETRY_PENDING"}:
        raise ValueError("unsupported retry ledger disposition")

    verified_at_text = getattr(verification, "verified_at_utc", None)
    verified_at = _parse_utc("verified_at_utc", verified_at_text)
    evaluated_text = _utc(evaluated_at)
    evaluated = datetime.fromisoformat(evaluated_text[:-1] + "+00:00")
    if evaluated < verified_at:
        raise ValueError("freshness evaluation cannot precede verification")

    age = (evaluated - verified_at).total_seconds()
    fresh = age <= max_age_seconds
    retry_permitted = fresh and disposition == "RETRY_PENDING"
    manual = disposition == "MANUAL_RESOLUTION" or (not fresh and disposition == "RETRY_PENDING")

    payload = {
        "schema": "morpheus-pilot-retry-ledger-verification-freshness-v1",
        "operation": operation,
        "key_sha256": key,
        "request_sha256": request,
        "verification_sha256": verification_id,
        "disposition": disposition,
        "verified_at_utc": verified_at_text,
        "evaluated_at_utc": evaluated_text,
        "max_age_seconds": max_age_seconds,
        "fresh": fresh,
        "retry_permitted": retry_permitted,
        "manual_resolution_required": manual,
    }
    return PilotRetryLedgerVerificationFreshness(**payload, freshness_sha256=_digest(payload))
