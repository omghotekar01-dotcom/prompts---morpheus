from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class PilotRetryBudgetAuthorization:
    schema: str
    operation: str
    key_sha256: str
    request_sha256: str
    budget_receipt_sha256: str
    budget_policy_sha256: str
    grant_policy_sha256: str
    executor_sha256: str
    authorization_sequence: int
    remaining_retry_executions_after_grant: int
    retry_authorized: bool
    granted_at: str
    authorization_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _require_sha256(name: str, value: Any) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def authorize_next_pilot_retry(
    budget_receipt: Any,
    *,
    grant_policy_sha256: str,
    executor_sha256: str,
    granted_at: datetime,
) -> PilotRetryBudgetAuthorization:
    """Issue a single next-retry authority only from a positive immutable budget receipt."""
    if getattr(budget_receipt, "schema", None) != "morpheus-pilot-retry-budget-receipt-v1":
        raise ValueError("unsupported retry budget receipt schema")

    key = _require_sha256("key_sha256", getattr(budget_receipt, "key_sha256", None))
    request = _require_sha256("request_sha256", getattr(budget_receipt, "request_sha256", None))
    budget_policy = _require_sha256("budget_policy_sha256", getattr(budget_receipt, "budget_policy_sha256", None))
    budget_receipt_id = _require_sha256("receipt_sha256", getattr(budget_receipt, "receipt_sha256", None))
    grant_policy = _require_sha256("grant_policy_sha256", grant_policy_sha256)
    executor = _require_sha256("executor_sha256", executor_sha256)
    if len({key, request, budget_policy, budget_receipt_id, grant_policy, executor}) != 6:
        raise ValueError("retry authorization evidence identities must be independent")

    available = getattr(budget_receipt, "retry_budget_available", None)
    manual = getattr(budget_receipt, "manual_resolution_required", None)
    if available is not True and available is not False:
        raise ValueError("retry_budget_available must be an exact boolean")
    if manual is not True and manual is not False:
        raise ValueError("manual_resolution_required must be an exact boolean")
    if available is not True or manual is not False:
        raise ValueError("retry budget receipt does not authorize another retry")

    execution_count = getattr(budget_receipt, "execution_count", None)
    remaining = getattr(budget_receipt, "remaining_retry_executions", None)
    maximum = getattr(budget_receipt, "max_retry_executions", None)
    for name, value in (("execution_count", execution_count), ("remaining_retry_executions", remaining), ("max_retry_executions", maximum)):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
    if execution_count < 1 or maximum < 1 or remaining != maximum - execution_count or remaining < 1:
        raise ValueError("retry budget arithmetic is inconsistent")

    if not isinstance(granted_at, datetime) or granted_at.tzinfo is None or granted_at.utcoffset() is None:
        raise ValueError("granted_at must be timezone-aware")
    normalized_time = granted_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    payload = {
        "schema": "morpheus-pilot-retry-budget-authorization-v1",
        "operation": getattr(budget_receipt, "operation", None),
        "key_sha256": key,
        "request_sha256": request,
        "budget_receipt_sha256": budget_receipt_id,
        "budget_policy_sha256": budget_policy,
        "grant_policy_sha256": grant_policy,
        "executor_sha256": executor,
        "authorization_sequence": execution_count + 1,
        "remaining_retry_executions_after_grant": remaining - 1,
        "retry_authorized": True,
        "granted_at": normalized_time,
    }
    return PilotRetryBudgetAuthorization(**payload, authorization_sha256=_digest(payload))
