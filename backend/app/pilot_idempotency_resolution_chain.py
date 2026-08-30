from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class PilotIdempotencyResolutionChain:
    schema: str
    operation: str
    key_sha256: str
    request_sha256: str
    receipt_sha256s: tuple[str, ...]
    latest_outcome: str
    retry_allowed: bool
    verified_at_utc: str
    chain_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value) or value == "0" * 64:
        raise ValueError(f"{field} must be a non-placeholder lowercase SHA-256 identity")
    return value


def _parse_utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be canonical UTC text")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field} must be valid ISO-8601 UTC text") from exc
    return parsed.astimezone(timezone.utc)


def _canonical_time(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("verified_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def verify_pilot_idempotency_resolution_chain(
    receipts: Iterable[Any], *, verified_at: datetime
) -> PilotIdempotencyResolutionChain:
    """Verify a chronological set of immutable ambiguity-resolution receipts.

    The chain is deliberately conservative: all receipts must refer to the same
    operation/key/request. Once any receipt confirms that a side effect exists,
    the resulting chain can never become retryable again.
    """

    items = tuple(receipts)
    if not items:
        raise ValueError("at least one resolution receipt is required")

    first = items[0]
    if getattr(first, "schema", None) != "morpheus-pilot-idempotency-resolution-receipt-v1":
        raise ValueError("unsupported resolution receipt schema")

    operation = getattr(first, "operation", None)
    if not isinstance(operation, str) or not operation:
        raise ValueError("receipt operation must be non-empty")
    key_sha256 = _sha(getattr(first, "key_sha256", None), "receipt.key_sha256")
    request_sha256 = _sha(getattr(first, "request_sha256", None), "receipt.request_sha256")

    receipt_ids: list[str] = []
    previous_time: datetime | None = None
    permanent_non_retryable = False
    latest_outcome = ""
    latest_retry = False

    for index, receipt in enumerate(items):
        if getattr(receipt, "schema", None) != "morpheus-pilot-idempotency-resolution-receipt-v1":
            raise ValueError(f"receipt[{index}] uses an unsupported schema")
        if getattr(receipt, "operation", None) != operation:
            raise ValueError("resolution chain operation changed")
        if getattr(receipt, "key_sha256", None) != key_sha256 or getattr(receipt, "request_sha256", None) != request_sha256:
            raise ValueError("resolution chain evidence lineage changed")

        receipt_id = _sha(getattr(receipt, "receipt_sha256", None), f"receipt[{index}].receipt_sha256")
        receipt_ids.append(receipt_id)
        current_time = _parse_utc(getattr(receipt, "exported_at_utc", None), f"receipt[{index}].exported_at_utc")
        if previous_time is not None and current_time < previous_time:
            raise ValueError("resolution receipts must be chronological")
        previous_time = current_time

        outcome = getattr(receipt, "outcome", None)
        retry_allowed = getattr(receipt, "retry_allowed", None)
        if not isinstance(retry_allowed, bool):
            raise ValueError("receipt.retry_allowed must be an exact boolean")
        if outcome == "CONFIRMED_SIDE_EFFECT_PRESENT":
            if retry_allowed:
                raise ValueError("side-effect-present evidence can never be retryable")
            permanent_non_retryable = True
        elif outcome == "CONFIRMED_NO_SIDE_EFFECT":
            if retry_allowed is not True:
                raise ValueError("no-side-effect evidence must be retryable")
        else:
            raise ValueError("unsupported resolution outcome")
        if permanent_non_retryable and retry_allowed:
            raise ValueError("a later receipt cannot restore retry authority after a confirmed side effect")
        latest_outcome, latest_retry = outcome, retry_allowed

    if len(set(receipt_ids)) != len(receipt_ids):
        raise ValueError("resolution receipt identities must be unique")

    payload = {
        "schema": "morpheus-pilot-idempotency-resolution-chain-v1",
        "operation": operation,
        "key_sha256": key_sha256,
        "request_sha256": request_sha256,
        "receipt_sha256s": tuple(receipt_ids),
        "latest_outcome": latest_outcome,
        "retry_allowed": False if permanent_non_retryable else latest_retry,
        "verified_at_utc": _canonical_time(verified_at),
    }
    return PilotIdempotencyResolutionChain(**payload, chain_sha256=_canonical_sha256(payload))
