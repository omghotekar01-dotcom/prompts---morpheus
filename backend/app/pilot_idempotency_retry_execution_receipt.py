from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_OUTCOMES = {"SUCCEEDED", "FAILED_NO_SIDE_EFFECT", "AMBIGUOUS"}


@dataclass(frozen=True)
class PilotIdempotencyRetryExecutionReceipt:
    schema: str
    operation: str
    key_sha256: str
    request_sha256: str
    authorization_sha256: str
    retry_request_sha256: str
    executor_artifact_sha256: str
    execution_evidence_sha256: str
    result_artifact_sha256: str
    outcome: str
    retry_consumed: bool
    follow_up_resolution_required: bool
    executed_at_utc: str
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value) or value == "0" * 64:
        raise ValueError(f"{field} must be a non-placeholder lowercase SHA-256 identity")
    return value


def _time(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("executed_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def record_pilot_idempotent_retry_execution(
    authorization: Any,
    *,
    execution_evidence_sha256: str,
    result_artifact_sha256: str,
    outcome: str,
    executed_at: datetime,
) -> PilotIdempotencyRetryExecutionReceipt:
    """Record one authorized retry execution without granting another retry.

    The authorization is single-use evidence: this receipt consumes it regardless of
    execution outcome. Ambiguous execution must return to the manual resolution path
    instead of being retried again from the same authorization.
    """
    if getattr(authorization, "schema", None) != "morpheus-pilot-idempotency-retry-authorization-v1":
        raise ValueError("unsupported retry authorization schema")
    if getattr(authorization, "authorized", None) is not True:
        raise ValueError("retry execution requires exact authorized=True evidence")
    if outcome not in _ALLOWED_OUTCOMES:
        raise ValueError(f"outcome must be one of {sorted(_ALLOWED_OUTCOMES)}")

    operation = getattr(authorization, "operation", None)
    if not isinstance(operation, str) or not operation:
        raise ValueError("authorization operation must be non-empty")

    identities = {
        "key_sha256": _sha(getattr(authorization, "key_sha256", None), "authorization.key_sha256"),
        "request_sha256": _sha(getattr(authorization, "request_sha256", None), "authorization.request_sha256"),
        "authorization_sha256": _sha(getattr(authorization, "authorization_sha256", None), "authorization.authorization_sha256"),
        "retry_request_sha256": _sha(getattr(authorization, "retry_request_sha256", None), "authorization.retry_request_sha256"),
        "executor_artifact_sha256": _sha(getattr(authorization, "executor_artifact_sha256", None), "authorization.executor_artifact_sha256"),
        "execution_evidence_sha256": _sha(execution_evidence_sha256, "execution_evidence_sha256"),
        "result_artifact_sha256": _sha(result_artifact_sha256, "result_artifact_sha256"),
    }
    if len(set(identities.values())) != len(identities):
        raise ValueError("retry execution evidence identities must be independent")

    payload = {
        "schema": "morpheus-pilot-idempotency-retry-execution-receipt-v1",
        "operation": operation,
        **identities,
        "outcome": outcome,
        "retry_consumed": True,
        "follow_up_resolution_required": outcome == "AMBIGUOUS",
        "executed_at_utc": _time(executed_at),
    }
    return PilotIdempotencyRetryExecutionReceipt(**payload, receipt_sha256=_digest(payload))
