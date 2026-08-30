from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_OPERATOR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@-]{2,127}$")
_OUTCOME_STATE = {
    "CONFIRMED_NO_SIDE_EFFECT": ("REMOVED_AFTER_CONFIRMED_NO_SIDE_EFFECT", True),
    "CONFIRMED_SIDE_EFFECT_PRESENT": ("RESOLVED_SIDE_EFFECT_PRESENT", False),
}


@dataclass(frozen=True)
class PilotIdempotencyResolutionReceipt:
    schema: str
    operation: str
    key_sha256: str
    request_sha256: str
    outcome: str
    operator_id: str
    reason_sha256: str
    resulting_state: str
    retry_allowed: bool
    authorization_evidence_hash: str
    applied_evidence_hash: str
    exported_at_utc: str
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value) or value == "0" * 64:
        raise ValueError(f"{field} must be a non-placeholder lowercase SHA-256 identity")
    return value


def _canonical_time(value: Any) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("exported_at must be a timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_pilot_idempotency_resolution_receipt(
    resolution: Mapping[str, Any], *, exported_at: datetime
) -> PilotIdempotencyResolutionReceipt:
    """Freeze one applied manual ambiguity resolution into a portable audit receipt.

    The receipt carries only identities already safe to persist. It deliberately
    excludes the raw incident reason and never performs or schedules a retry.
    """

    if not isinstance(resolution, Mapping):
        raise ValueError("resolution must be a mapping")
    if resolution.get("schema") != "morpheus-idempotency-operator-resolution-v1":
        raise ValueError("unsupported idempotency resolution schema")

    operation = resolution.get("operation")
    if not isinstance(operation, str) or not operation.strip() or len(operation.strip()) > 128:
        raise ValueError("operation must contain 1-128 characters")
    operation = operation.strip()

    outcome = resolution.get("outcome")
    if outcome not in _OUTCOME_STATE:
        raise ValueError("unsupported resolution outcome")
    expected_state, expected_retry = _OUTCOME_STATE[outcome]

    resulting_state = resolution.get("resulting_state")
    retry_allowed = resolution.get("retry_allowed")
    if resulting_state != expected_state:
        raise ValueError("resolution state is inconsistent with outcome")
    if retry_allowed is not expected_retry:
        raise ValueError("retry_allowed must be the exact boolean implied by outcome")

    operator_id = resolution.get("operator_id")
    if not isinstance(operator_id, str) or not _OPERATOR_RE.fullmatch(operator_id):
        raise ValueError("operator_id must be a canonical 3-128 character identity")

    identities = {
        "key_sha256": _sha(resolution.get("key_sha256"), "key_sha256"),
        "request_sha256": _sha(resolution.get("request_sha256"), "request_sha256"),
        "reason_sha256": _sha(resolution.get("reason_sha256"), "reason_sha256"),
        "authorization_evidence_hash": _sha(
            resolution.get("authorization_evidence_hash"), "authorization_evidence_hash"
        ),
        "applied_evidence_hash": _sha(resolution.get("applied_evidence_hash"), "applied_evidence_hash"),
    }
    if len(set(identities.values())) != len(identities):
        raise ValueError("resolution receipt evidence identities must be independent")

    payload = {
        "schema": "morpheus-pilot-idempotency-resolution-receipt-v1",
        "operation": operation,
        **identities,
        "outcome": outcome,
        "operator_id": operator_id,
        "resulting_state": resulting_state,
        "retry_allowed": retry_allowed,
        "exported_at_utc": _canonical_time(exported_at),
    }
    return PilotIdempotencyResolutionReceipt(**payload, receipt_sha256=_canonical_sha256(payload))
