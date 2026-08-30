from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

_HEX = frozenset("0123456789abcdef")
_ALLOWED_OUTCOMES = frozenset({"SUCCEEDED", "FAILED_NO_SIDE_EFFECT", "AMBIGUOUS"})


def _sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in _HEX for ch in value):
        raise ValueError(f"{label} must be a lowercase SHA-256 hex digest")
    return value


@dataclass(frozen=True)
class PilotRetryExecutionHistory:
    schema: str
    operation: str
    key_sha256: str
    request_sha256: str
    execution_count: int
    ambiguous_count: int
    latest_outcome: str
    manual_resolution_required: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_pilot_retry_execution_history(receipts: Iterable[Any]) -> PilotRetryExecutionHistory:
    """Validate a single-request, single-use retry history and fail closed on malformed evidence."""
    items = list(receipts)
    if not items:
        raise ValueError("at least one retry execution receipt is required")

    operation = getattr(items[0], "operation", None)
    if not isinstance(operation, str) or not operation.strip():
        raise ValueError("operation must be non-empty")
    operation = operation.strip()
    key = _sha256(getattr(items[0], "key_sha256", None), "key_sha256")
    request = _sha256(getattr(items[0], "request_sha256", None), "request_sha256")
    if key == request:
        raise ValueError("key and request evidence identities must be independent")

    seen_receipts: set[str] = set()
    seen_retry_grants: set[str] = set()
    ambiguous_count = 0
    for index, receipt in enumerate(items):
        if getattr(receipt, "schema", None) != "morpheus-pilot-idempotency-retry-execution-receipt-v1":
            raise ValueError("unsupported retry execution receipt schema")
        if getattr(receipt, "operation", None) != operation:
            raise ValueError("operation changed within retry execution history")
        if _sha256(getattr(receipt, "key_sha256", None), "key_sha256") != key or _sha256(
            getattr(receipt, "request_sha256", None), "request_sha256"
        ) != request:
            raise ValueError("request lineage changed within retry execution history")
        if getattr(receipt, "retry_consumed", None) is not True:
            raise ValueError("retry receipt must carry retry_consumed=True")

        receipt_id = _sha256(getattr(receipt, "receipt_sha256", None), "receipt_sha256")
        grant_id = _sha256(getattr(receipt, "authorization_sha256", None), "authorization_sha256")
        if len({key, request, receipt_id, grant_id}) != 4:
            raise ValueError("retry history evidence identities must be independent")
        if receipt_id in seen_receipts:
            raise ValueError("duplicate retry execution receipt")
        if grant_id in seen_retry_grants:
            raise ValueError("one retry grant cannot be consumed twice")
        seen_receipts.add(receipt_id)
        seen_retry_grants.add(grant_id)

        outcome = getattr(receipt, "outcome", None)
        if outcome not in _ALLOWED_OUTCOMES:
            raise ValueError("unsupported retry execution outcome")
        ambiguous = outcome == "AMBIGUOUS"
        if getattr(receipt, "follow_up_resolution_required", None) is not ambiguous:
            raise ValueError("follow-up resolution flag is inconsistent")
        if ambiguous:
            ambiguous_count += 1
            if index != len(items) - 1:
                raise ValueError("ambiguous execution must be terminal pending manual resolution")

    latest_outcome = getattr(items[-1], "outcome")
    return PilotRetryExecutionHistory(
        schema="morpheus-pilot-retry-execution-history-v2",
        operation=operation,
        key_sha256=key,
        request_sha256=request,
        execution_count=len(items),
        ambiguous_count=ambiguous_count,
        latest_outcome=latest_outcome,
        manual_resolution_required=latest_outcome == "AMBIGUOUS",
    )
