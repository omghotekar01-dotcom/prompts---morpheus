from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class PilotRetryBudgetReceipt:
    schema: str
    operation: str
    key_sha256: str
    request_sha256: str
    budget_policy_sha256: str
    execution_count: int
    max_retry_executions: int
    remaining_retry_executions: int
    retry_budget_available: bool
    manual_resolution_required: bool
    evaluated_at: str
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _require_sha256(name: str, value: Any) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def issue_pilot_retry_budget_receipt(
    decision: Any,
    *,
    budget_policy_sha256: str,
    evaluated_at: datetime,
) -> PilotRetryBudgetReceipt:
    """Freeze a retry-budget decision and its governing policy into immutable evidence."""
    if getattr(decision, "schema", None) != "morpheus-pilot-retry-budget-decision-v1":
        raise ValueError("unsupported retry budget decision schema")
    policy = _require_sha256("budget_policy_sha256", budget_policy_sha256)
    key_sha256 = _require_sha256("key_sha256", getattr(decision, "key_sha256", None))
    request_sha256 = _require_sha256("request_sha256", getattr(decision, "request_sha256", None))
    if len({policy, key_sha256, request_sha256}) != 3:
        raise ValueError("budget policy, key, and request evidence must be independent")
    if not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise ValueError("evaluated_at must be timezone-aware")

    retry_budget_available = getattr(decision, "retry_budget_available", None)
    manual_resolution_required = getattr(decision, "manual_resolution_required", None)
    if retry_budget_available is not True and retry_budget_available is not False:
        raise ValueError("retry_budget_available must be an exact boolean")
    if manual_resolution_required is not True and manual_resolution_required is not False:
        raise ValueError("manual_resolution_required must be an exact boolean")
    if retry_budget_available and manual_resolution_required:
        raise ValueError("retry budget cannot be available while manual resolution is required")

    execution_count = getattr(decision, "execution_count", None)
    maximum = getattr(decision, "max_retry_executions", None)
    remaining = getattr(decision, "remaining_retry_executions", None)
    for name, value in (("execution_count", execution_count), ("max_retry_executions", maximum), ("remaining_retry_executions", remaining)):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
    if execution_count < 1 or maximum < 1 or execution_count > maximum or remaining != maximum - execution_count:
        raise ValueError("retry budget arithmetic is inconsistent")

    normalized_time = evaluated_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = {
        "schema": "morpheus-pilot-retry-budget-receipt-v1",
        "operation": getattr(decision, "operation", None),
        "key_sha256": key_sha256,
        "request_sha256": request_sha256,
        "budget_policy_sha256": policy,
        "execution_count": execution_count,
        "max_retry_executions": maximum,
        "remaining_retry_executions": remaining,
        "retry_budget_available": retry_budget_available,
        "manual_resolution_required": manual_resolution_required,
        "evaluated_at": normalized_time,
    }
    return PilotRetryBudgetReceipt(**payload, receipt_sha256=_digest(payload))
