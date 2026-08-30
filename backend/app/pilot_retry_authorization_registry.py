from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Any, Iterable

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class PilotRetryAuthorizationRegistry:
    schema: str
    operation: str
    key_sha256: str
    request_sha256: str
    authorization_sha256: str
    authorization_sequence: int
    consumed_authorization_sha256s: tuple[str, ...]
    authorization_consumed: bool
    registry_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _sha(name: str, value: Any) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def register_retry_authorization_consumption(
    authorization: Any,
    *,
    consumed_authorization_sha256s: Iterable[str] = (),
) -> PilotRetryAuthorizationRegistry:
    """Consume one retry authorization exactly once before execution begins."""
    if getattr(authorization, "schema", None) != "morpheus-pilot-retry-budget-authorization-v1":
        raise ValueError("unsupported retry authorization schema")
    if getattr(authorization, "retry_authorized", None) is not True:
        raise ValueError("authorization must explicitly authorize retry")

    key = _sha("key_sha256", getattr(authorization, "key_sha256", None))
    request = _sha("request_sha256", getattr(authorization, "request_sha256", None))
    authorization_id = _sha("authorization_sha256", getattr(authorization, "authorization_sha256", None))
    sequence = getattr(authorization, "authorization_sequence", None)
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 2:
        raise ValueError("authorization_sequence must be an integer >= 2")

    consumed = tuple(_sha("consumed authorization", item) for item in consumed_authorization_sha256s)
    if len(set(consumed)) != len(consumed):
        raise ValueError("consumed authorization registry contains duplicates")
    if authorization_id in consumed:
        raise ValueError("retry authorization has already been consumed")
    if authorization_id in {key, request} or key == request:
        raise ValueError("authorization and request evidence identities must be independent")

    updated = tuple(sorted((*consumed, authorization_id)))
    payload = {
        "schema": "morpheus-pilot-retry-authorization-registry-v1",
        "operation": getattr(authorization, "operation", None),
        "key_sha256": key,
        "request_sha256": request,
        "authorization_sha256": authorization_id,
        "authorization_sequence": sequence,
        "consumed_authorization_sha256s": updated,
        "authorization_consumed": True,
    }
    return PilotRetryAuthorizationRegistry(**payload, registry_sha256=_digest(payload))
