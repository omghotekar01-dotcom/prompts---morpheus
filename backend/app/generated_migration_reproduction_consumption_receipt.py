from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class MigrationReproductionConsumptionReceipt:
    schema: str
    consumption_sha256: str
    attestation_sha256: str
    consumer_artifact_sha256: str
    purpose: str
    observed_at: str
    observer_artifact_sha256: str
    predecessor_receipt_sha256: str | None
    reproduction_authorized: bool
    receipt_sha256: str


def _hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value) or value == "0" * 64:
        raise ValueError(f"{field} must be a non-placeholder lowercase SHA-256 identity")
    return value


def _timestamp(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("observed_at must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("observed_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def record_generated_migration_reproduction_consumption(
    *,
    consumption: Any,
    observed_at: str,
    observer_artifact_sha256: str,
    predecessor_receipt_sha256: str | None = None,
) -> MigrationReproductionConsumptionReceipt:
    if getattr(consumption, "reproduction_authorized", None) is not True:
        raise ValueError("consumption must be explicitly reproduction-authorized")
    consumption_id = _hash(getattr(consumption, "consumption_sha256", None), "consumption.consumption_sha256")
    attestation_id = _hash(getattr(consumption, "attestation_sha256", None), "consumption.attestation_sha256")
    consumer_id = _hash(getattr(consumption, "consumer_artifact_sha256", None), "consumption.consumer_artifact_sha256")
    observer_id = _hash(observer_artifact_sha256, "observer_artifact_sha256")
    predecessor_id = None if predecessor_receipt_sha256 is None else _hash(predecessor_receipt_sha256, "predecessor_receipt_sha256")
    purpose = getattr(consumption, "purpose", None)
    if not isinstance(purpose, str) or not purpose:
        raise ValueError("consumption.purpose must be non-empty")
    identities = [consumption_id, attestation_id, consumer_id, observer_id]
    if predecessor_id is not None:
        identities.append(predecessor_id)
    if len(set(identities)) != len(identities):
        raise ValueError("receipt identities must be independent")
    payload = {
        "schema": "morpheus.generated_migration_reproduction_consumption_receipt.v1",
        "consumption_sha256": consumption_id,
        "attestation_sha256": attestation_id,
        "consumer_artifact_sha256": consumer_id,
        "purpose": purpose,
        "observed_at": _timestamp(observed_at),
        "observer_artifact_sha256": observer_id,
        "predecessor_receipt_sha256": predecessor_id,
        "reproduction_authorized": True,
    }
    return MigrationReproductionConsumptionReceipt(**payload, receipt_sha256=_canonical_sha256(payload))
