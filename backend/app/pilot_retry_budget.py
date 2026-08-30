from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class PilotRetryBudgetDecision:
    schema: str
    operation: str
    key_sha256: str
    request_sha256: str
    execution_count: int
    max_retry_executions: int
    remaining_retry_executions: int
    retry_budget_available: bool
    manual_resolution_required: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_pilot_retry_budget(history: Any, *, max_retry_executions: int) -> PilotRetryBudgetDecision:
    """Bound repeated pilot retries so FAILED_NO_SIDE_EFFECT cannot loop forever."""
    if getattr(history, "schema", None) != "morpheus-pilot-retry-execution-history-v2":
        raise ValueError("unsupported retry execution history schema")
    if not isinstance(max_retry_executions, int) or isinstance(max_retry_executions, bool) or max_retry_executions < 1:
        raise ValueError("max_retry_executions must be a positive integer")

    execution_count = getattr(history, "execution_count", None)
    if not isinstance(execution_count, int) or isinstance(execution_count, bool) or execution_count < 1:
        raise ValueError("execution_count must be a positive integer")
    if execution_count > max_retry_executions:
        raise ValueError("retry history exceeds configured retry budget")

    manual_resolution_required = getattr(history, "manual_resolution_required", None)
    if manual_resolution_required is not True and manual_resolution_required is not False:
        raise ValueError("manual_resolution_required must be an exact boolean")

    latest_outcome = getattr(history, "latest_outcome", None)
    if latest_outcome not in {"SUCCEEDED", "FAILED_NO_SIDE_EFFECT", "AMBIGUOUS"}:
        raise ValueError("unsupported latest retry outcome")
    if manual_resolution_required is not (latest_outcome == "AMBIGUOUS"):
        raise ValueError("manual-resolution state is inconsistent with latest outcome")

    remaining = max_retry_executions - execution_count
    retry_budget_available = latest_outcome == "FAILED_NO_SIDE_EFFECT" and remaining > 0 and not manual_resolution_required

    return PilotRetryBudgetDecision(
        schema="morpheus-pilot-retry-budget-decision-v1",
        operation=getattr(history, "operation"),
        key_sha256=getattr(history, "key_sha256"),
        request_sha256=getattr(history, "request_sha256"),
        execution_count=execution_count,
        max_retry_executions=max_retry_executions,
        remaining_retry_executions=remaining,
        retry_budget_available=retry_budget_available,
        manual_resolution_required=manual_resolution_required or (latest_outcome == "FAILED_NO_SIDE_EFFECT" and remaining == 0),
    )
