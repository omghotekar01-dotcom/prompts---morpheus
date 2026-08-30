from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class MigrationReproductionConsumptionChain:
    schema: str
    attestation_sha256: str
    purpose: str
    receipt_sha256s: tuple[str, ...]
    consumer_artifact_sha256s: tuple[str, ...]
    first_observed_at: str
    last_observed_at: str
    receipt_count: int
    reproduction_authorized: bool
    chain_sha256: str


def _hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value) or value == "0" * 64:
        raise ValueError(f"{field} must be a non-placeholder lowercase SHA-256 identity")
    return value


def _time(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def verify_generated_migration_reproduction_consumption_chain(
    receipts: Sequence[Any],
) -> MigrationReproductionConsumptionChain:
    if not isinstance(receipts, Sequence) or isinstance(receipts, (str, bytes, bytearray)) or not receipts:
        raise ValueError("receipts must be a non-empty sequence")

    receipt_ids: list[str] = []
    consumer_ids: list[str] = []
    observed: list[datetime] = []
    attestation_id: str | None = None
    purpose: str | None = None
    predecessor: str | None = None

    for index, receipt in enumerate(receipts):
        if getattr(receipt, "reproduction_authorized", None) is not True:
            raise ValueError("every receipt must be explicitly reproduction-authorized")
        receipt_id = _hash(getattr(receipt, "receipt_sha256", None), f"receipts[{index}].receipt_sha256")
        current_attestation = _hash(getattr(receipt, "attestation_sha256", None), f"receipts[{index}].attestation_sha256")
        consumer_id = _hash(getattr(receipt, "consumer_artifact_sha256", None), f"receipts[{index}].consumer_artifact_sha256")
        current_purpose = getattr(receipt, "purpose", None)
        if not isinstance(current_purpose, str) or not current_purpose:
            raise ValueError("every receipt purpose must be non-empty")
        current_predecessor = getattr(receipt, "predecessor_receipt_sha256", None)
        if current_predecessor is not None:
            current_predecessor = _hash(current_predecessor, f"receipts[{index}].predecessor_receipt_sha256")
        if current_predecessor != predecessor:
            raise ValueError("reproduction consumption receipt chain is broken")
        when = _time(getattr(receipt, "observed_at", None), f"receipts[{index}].observed_at")
        if observed and when < observed[-1]:
            raise ValueError("receipt observation time must be monotonic")
        if attestation_id is None:
            attestation_id = current_attestation
            purpose = current_purpose
        elif current_attestation != attestation_id or current_purpose != purpose:
            raise ValueError("receipt chain must preserve attestation and purpose")
        receipt_ids.append(receipt_id)
        consumer_ids.append(consumer_id)
        observed.append(when)
        predecessor = receipt_id

    if len(set(receipt_ids)) != len(receipt_ids):
        raise ValueError("receipt identities must be unique")
    if len(set(consumer_ids)) != len(consumer_ids):
        raise ValueError("consumer artifacts must be independent across the chain")

    payload = {
        "schema": "morpheus.generated_migration_reproduction_consumption_chain.v1",
        "attestation_sha256": attestation_id,
        "purpose": purpose,
        "receipt_sha256s": receipt_ids,
        "consumer_artifact_sha256s": consumer_ids,
        "first_observed_at": getattr(receipts[0], "observed_at"),
        "last_observed_at": getattr(receipts[-1], "observed_at"),
        "receipt_count": len(receipt_ids),
        "reproduction_authorized": True,
    }
    return MigrationReproductionConsumptionChain(
        **payload,
        receipt_sha256s=tuple(receipt_ids),
        consumer_artifact_sha256s=tuple(consumer_ids),
        chain_sha256=_canonical_sha256(payload),
    )
