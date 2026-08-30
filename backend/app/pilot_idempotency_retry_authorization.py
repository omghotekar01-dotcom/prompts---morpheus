from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class PilotIdempotencyRetryAuthorization:
    schema: str
    operation: str
    key_sha256: str
    request_sha256: str
    resolution_chain_sha256: str
    retry_request_sha256: str
    executor_artifact_sha256: str
    authorized: bool
    authorized_at_utc: str
    authorization_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value) or value == "0" * 64:
        raise ValueError(f"{field} must be a non-placeholder lowercase SHA-256 identity")
    return value


def _time(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("authorized_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def authorize_pilot_idempotent_retry(
    chain: Any,
    *,
    retry_request_sha256: str,
    executor_artifact_sha256: str,
    authorized_at: datetime,
) -> PilotIdempotencyRetryAuthorization:
    """Authorize a retry only from an explicitly retryable verified resolution chain.

    This function emits evidence; it never performs the retry. A chain that ever
    observed a side effect is non-retryable by construction in the chain verifier.
    """
    if getattr(chain, "schema", None) != "morpheus-pilot-idempotency-resolution-chain-v1":
        raise ValueError("unsupported resolution chain schema")
    if getattr(chain, "retry_allowed", None) is not True:
        raise ValueError("resolution chain does not authorize retry")
    if getattr(chain, "latest_outcome", None) != "CONFIRMED_NO_SIDE_EFFECT":
        raise ValueError("retry requires confirmed no-side-effect evidence")

    operation = getattr(chain, "operation", None)
    if not isinstance(operation, str) or not operation:
        raise ValueError("chain operation must be non-empty")

    identities = {
        "key_sha256": _sha(getattr(chain, "key_sha256", None), "chain.key_sha256"),
        "request_sha256": _sha(getattr(chain, "request_sha256", None), "chain.request_sha256"),
        "resolution_chain_sha256": _sha(getattr(chain, "chain_sha256", None), "chain.chain_sha256"),
        "retry_request_sha256": _sha(retry_request_sha256, "retry_request_sha256"),
        "executor_artifact_sha256": _sha(executor_artifact_sha256, "executor_artifact_sha256"),
    }
    if len(set(identities.values())) != len(identities):
        raise ValueError("retry authorization evidence identities must be independent")

    payload = {
        "schema": "morpheus-pilot-idempotency-retry-authorization-v1",
        "operation": operation,
        **identities,
        "authorized": True,
        "authorized_at_utc": _time(authorized_at),
    }
    return PilotIdempotencyRetryAuthorization(**payload, authorization_sha256=_digest(payload))
