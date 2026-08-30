from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED = {"COMPLETED", "MANUAL_RESOLUTION", "RETRY_PENDING"}


@dataclass(frozen=True)
class PilotRetryLedgerSeal:
    schema: str
    operation: str
    key_sha256: str
    request_sha256: str
    ledger_sha256: str
    policy_sha256: str
    disposition: str
    sealed_at_utc: str
    terminal: bool
    manual_resolution_required: bool
    retry_requires_new_authorization: bool
    seal_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha(name: str, value: Any) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _utc(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("sealed_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def seal_retry_execution_ledger(ledger: Any, *, policy_sha256: str, sealed_at: datetime) -> PilotRetryLedgerSeal:
    if getattr(ledger, "schema", None) != "morpheus-pilot-retry-execution-ledger-v1":
        raise ValueError("unsupported retry execution ledger schema")
    operation = getattr(ledger, "operation", None)
    if not isinstance(operation, str) or not operation.strip() or operation != operation.strip():
        raise ValueError("operation must be canonical non-empty text")
    key = _sha("key_sha256", getattr(ledger, "key_sha256", None))
    request = _sha("request_sha256", getattr(ledger, "request_sha256", None))
    ledger_id = _sha("ledger_sha256", getattr(ledger, "ledger_sha256", None))
    policy = _sha("policy_sha256", policy_sha256)
    if len({key, request, ledger_id, policy}) != 4:
        raise ValueError("retry seal evidence identities must be independent")

    terminal = getattr(ledger, "terminal", None)
    manual = getattr(ledger, "manual_resolution_required", None)
    retry = getattr(ledger, "retry_requires_new_authorization", None)
    if not all(isinstance(v, bool) for v in (terminal, manual, retry)):
        raise ValueError("ledger state flags must be exact booleans")
    if manual:
        disposition = "MANUAL_RESOLUTION"
        if not terminal or retry:
            raise ValueError("manual-resolution ledger state is contradictory")
    elif terminal:
        disposition = "COMPLETED"
        if retry:
            raise ValueError("terminal ledger cannot require another retry")
    else:
        disposition = "RETRY_PENDING"
        if not retry:
            raise ValueError("non-terminal ledger must require fresh retry authorization")
    if disposition not in _ALLOWED:
        raise ValueError("unsupported retry ledger disposition")

    payload = {
        "schema": "morpheus-pilot-retry-ledger-seal-v1",
        "operation": operation,
        "key_sha256": key,
        "request_sha256": request,
        "ledger_sha256": ledger_id,
        "policy_sha256": policy,
        "disposition": disposition,
        "sealed_at_utc": _utc(sealed_at),
        "terminal": terminal,
        "manual_resolution_required": manual,
        "retry_requires_new_authorization": retry,
    }
    return PilotRetryLedgerSeal(**payload, seal_sha256=_digest(payload))
