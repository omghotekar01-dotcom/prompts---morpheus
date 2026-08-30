from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class PilotRetryExecutionHistory:
    schema: str
    operation: str
    execution_count: int
    ambiguous_count: int
    latest_outcome: str
    manual_resolution_required: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_pilot_retry_execution_history(receipts: Iterable[Any]) -> PilotRetryExecutionHistory:
    """Validate that retry receipts form a safe single-use execution history."""
    items = list(receipts)
    if not items:
        raise ValueError("at least one retry execution receipt is required")

    operation = getattr(items[0], "operation", None)
    key = getattr(items[0], "key_sha256", None)
    request = getattr(items[0], "request_sha256", None)
    if not isinstance(operation, str) or not operation:
        raise ValueError("operation must be non-empty")

    seen_receipts: set[str] = set()
    seen_retry_grants: set[str] = set()
    ambiguous_count = 0
    for index, receipt in enumerate(items):
        if getattr(receipt, "schema", None) != "morpheus-pilot-idempotency-retry-execution-receipt-v1":
            raise ValueError("unsupported retry execution receipt schema")
        if getattr(receipt, "operation", None) != operation:
            raise ValueError("operation changed within retry execution history")
        if getattr(receipt, "key_sha256", None) != key or getattr(receipt, "request_sha256", None) != request:
            raise ValueError("request lineage changed within retry execution history")
        if getattr(receipt, "retry_consumed", None) is not True:
            raise ValueError("retry receipt must carry retry_consumed=True")

        receipt_id = getattr(receipt, "receipt_sha256", None)
        grant_id = getattr(receipt, "authorization_sha256", None)
        if not isinstance(receipt_id, str) or len(receipt_id) != 64:
            raise ValueError("receipt identity is invalid")
        if not isinstance(grant_id, str) or len(grant_id) != 64:
            raise ValueError("retry grant identity is invalid")
        if receipt_id in seen_receipts:
            raise ValueError("duplicate retry execution receipt")
        if grant_id in seen_retry_grants:
            raise ValueError("one retry grant cannot be consumed twice")
        seen_receipts.add(receipt_id)
        seen_retry_grants.add(grant_id)

        ambiguous = getattr(receipt, "outcome", None) == "AMBIGUOUS"
        if getattr(receipt, "follow_up_resolution_required", None) is not ambiguous:
            raise ValueError("follow-up resolution flag is inconsistent")
        if ambiguous:
            ambiguous_count += 1
            if index != len(items) - 1:
                raise ValueError("ambiguous execution must be terminal pending manual resolution")

    latest_outcome = getattr(items[-1], "outcome", None)
    return PilotRetryExecutionHistory(
        schema="morpheus-pilot-retry-execution-history-v1",
        operation=operation,
        execution_count=len(items),
        ambiguous_count=ambiguous_count,
        latest_outcome=latest_outcome,
        manual_resolution_required=latest_outcome == "AMBIGUOUS",
    )
