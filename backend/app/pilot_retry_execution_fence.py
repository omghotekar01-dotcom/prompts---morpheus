from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_OUTCOMES = {"SUCCEEDED", "FAILED_NO_SIDE_EFFECT", "AMBIGUOUS"}


@dataclass(frozen=True)
class PilotRetryExecutionFenceReceipt:
    schema: str
    operation: str
    key_sha256: str
    request_sha256: str
    authorization_sha256: str
    registry_sha256: str
    authorization_sequence: int
    executor_sha256: str
    outcome: str
    executed_at_utc: str
    authorization_consumed: bool
    retry_may_repeat_without_new_authorization: bool
    manual_resolution_required: bool
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _sha(name: str, value: Any) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _utc(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("executed_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def fence_retry_execution(
    authorization: Any,
    registry: Any,
    *,
    executor_sha256: str,
    outcome: str,
    executed_at: datetime,
) -> PilotRetryExecutionFenceReceipt:
    """Bind an executed retry to the exact single-use authorization consumption evidence."""
    if getattr(authorization, "schema", None) != "morpheus-pilot-retry-budget-authorization-v1":
        raise ValueError("unsupported retry authorization schema")
    if getattr(registry, "schema", None) != "morpheus-pilot-retry-authorization-registry-v1":
        raise ValueError("unsupported authorization registry schema")
    if getattr(authorization, "retry_authorized", None) is not True:
        raise ValueError("retry authorization must be explicitly true")
    if getattr(registry, "authorization_consumed", None) is not True:
        raise ValueError("authorization must be consumed before execution")
    if outcome not in _ALLOWED_OUTCOMES:
        raise ValueError("unsupported retry execution outcome")

    operation = getattr(authorization, "operation", None)
    if not isinstance(operation, str) or not operation.strip():
        raise ValueError("operation is required")
    if getattr(registry, "operation", None) != operation:
        raise ValueError("registry operation does not match authorization")

    key = _sha("key_sha256", getattr(authorization, "key_sha256", None))
    request = _sha("request_sha256", getattr(authorization, "request_sha256", None))
    authorization_id = _sha("authorization_sha256", getattr(authorization, "authorization_sha256", None))
    registry_id = _sha("registry_sha256", getattr(registry, "registry_sha256", None))
    executor = _sha("executor_sha256", executor_sha256)

    if getattr(registry, "key_sha256", None) != key or getattr(registry, "request_sha256", None) != request:
        raise ValueError("registry request lineage does not match authorization")
    if getattr(registry, "authorization_sha256", None) != authorization_id:
        raise ValueError("registry does not consume this authorization")

    sequence = getattr(authorization, "authorization_sequence", None)
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 2:
        raise ValueError("authorization_sequence must be an integer >= 2")
    if getattr(registry, "authorization_sequence", None) != sequence:
        raise ValueError("registry authorization sequence does not match")

    evidence = {key, request, authorization_id, registry_id, executor}
    if len(evidence) != 5:
        raise ValueError("execution evidence identities must be independent")

    manual_resolution_required = outcome == "AMBIGUOUS"
    payload = {
        "schema": "morpheus-pilot-retry-execution-fence-v1",
        "operation": operation,
        "key_sha256": key,
        "request_sha256": request,
        "authorization_sha256": authorization_id,
        "registry_sha256": registry_id,
        "authorization_sequence": sequence,
        "executor_sha256": executor,
        "outcome": outcome,
        "executed_at_utc": _utc(executed_at),
        "authorization_consumed": True,
        "retry_may_repeat_without_new_authorization": False,
        "manual_resolution_required": manual_resolution_required,
    }
    return PilotRetryExecutionFenceReceipt(**payload, receipt_sha256=_digest(payload))
