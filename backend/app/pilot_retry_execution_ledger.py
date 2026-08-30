from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Iterable

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_OUTCOMES = {"SUCCEEDED", "FAILED_NO_SIDE_EFFECT", "AMBIGUOUS"}
_TERMINAL_OUTCOMES = {"SUCCEEDED", "AMBIGUOUS"}


@dataclass(frozen=True)
class PilotRetryExecutionLedger:
    schema: str
    operation: str
    key_sha256: str
    request_sha256: str
    execution_count: int
    first_authorization_sequence: int
    last_authorization_sequence: int
    latest_outcome: str
    latest_executed_at_utc: str
    terminal: bool
    manual_resolution_required: bool
    retry_requires_new_authorization: bool
    ledger_sha256: str

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
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError(f"{name} must be canonical UTC")
    canonical = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if canonical != value:
        raise ValueError(f"{name} must be canonical UTC")
    return parsed


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_retry_execution_ledger(receipts: Iterable[Any]) -> PilotRetryExecutionLedger:
    """Validate retry executions as one ordered lineage and preserve terminal outcomes."""
    items = list(receipts)
    if not items:
        raise ValueError("at least one retry execution receipt is required")

    first = items[0]
    if getattr(first, "schema", None) != "morpheus-pilot-retry-execution-fence-v1":
        raise ValueError("unsupported retry execution receipt schema")

    operation = getattr(first, "operation", None)
    if not isinstance(operation, str) or not operation.strip():
        raise ValueError("operation is required")
    key = _sha("key_sha256", getattr(first, "key_sha256", None))
    request = _sha("request_sha256", getattr(first, "request_sha256", None))

    seen_receipts: set[str] = set()
    previous_sequence: int | None = None
    previous_time: datetime | None = None
    terminal_seen = False

    for index, receipt in enumerate(items):
        if getattr(receipt, "schema", None) != "morpheus-pilot-retry-execution-fence-v1":
            raise ValueError("unsupported retry execution receipt schema")
        if getattr(receipt, "operation", None) != operation or getattr(receipt, "key_sha256", None) != key or getattr(receipt, "request_sha256", None) != request:
            raise ValueError("retry execution lineage changed")
        if getattr(receipt, "authorization_consumed", None) is not True or getattr(receipt, "retry_may_repeat_without_new_authorization", None) is not False:
            raise ValueError("retry execution receipt violates single-use authorization semantics")

        receipt_id = _sha("receipt_sha256", getattr(receipt, "receipt_sha256", None))
        if receipt_id in seen_receipts:
            raise ValueError("duplicate retry execution receipt")
        seen_receipts.add(receipt_id)

        sequence = getattr(receipt, "authorization_sequence", None)
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 2:
            raise ValueError("authorization_sequence must be an integer >= 2")
        if previous_sequence is not None and sequence != previous_sequence + 1:
            raise ValueError("retry authorization sequence must be contiguous")

        outcome = getattr(receipt, "outcome", None)
        if outcome not in _ALLOWED_OUTCOMES:
            raise ValueError("unsupported retry execution outcome")
        manual = getattr(receipt, "manual_resolution_required", None)
        if not isinstance(manual, bool) or manual is not (outcome == "AMBIGUOUS"):
            raise ValueError("manual-resolution flag contradicts retry outcome")

        executed_at = _parse_utc("executed_at_utc", getattr(receipt, "executed_at_utc", None))
        if previous_time is not None and executed_at <= previous_time:
            raise ValueError("retry execution timestamps must be strictly increasing")
        if terminal_seen:
            raise ValueError("retry execution cannot continue after a terminal outcome")

        terminal_seen = outcome in _TERMINAL_OUTCOMES
        previous_sequence = sequence
        previous_time = executed_at

    latest = items[-1]
    latest_outcome = getattr(latest, "outcome")
    payload = {
        "schema": "morpheus-pilot-retry-execution-ledger-v1",
        "operation": operation,
        "key_sha256": key,
        "request_sha256": request,
        "execution_count": len(items),
        "first_authorization_sequence": getattr(items[0], "authorization_sequence"),
        "last_authorization_sequence": getattr(latest, "authorization_sequence"),
        "latest_outcome": latest_outcome,
        "latest_executed_at_utc": getattr(latest, "executed_at_utc"),
        "terminal": latest_outcome in _TERMINAL_OUTCOMES,
        "manual_resolution_required": latest_outcome == "AMBIGUOUS",
        "retry_requires_new_authorization": latest_outcome == "FAILED_NO_SIDE_EFFECT",
    }
    return PilotRetryExecutionLedger(**payload, ledger_sha256=_digest(payload))
