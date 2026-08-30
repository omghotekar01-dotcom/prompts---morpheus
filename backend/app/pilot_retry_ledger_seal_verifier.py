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
class PilotRetryLedgerSealVerification:
    schema: str
    operation: str
    key_sha256: str
    request_sha256: str
    ledger_sha256: str
    policy_sha256: str
    seal_sha256: str
    disposition: str
    verified_at_utc: str
    verified: bool
    verification_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha(name: str, value: Any) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _canonical_utc(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{name} must be canonical UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{name} must be canonical UTC") from exc
    canonical = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if canonical != value:
        raise ValueError(f"{name} must be canonical UTC")
    return value


def _utc(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("verified_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def verify_retry_ledger_seal(
    seal: Any,
    *,
    expected_operation: str,
    expected_key_sha256: str,
    expected_request_sha256: str,
    verified_at: datetime,
) -> PilotRetryLedgerSealVerification:
    if getattr(seal, "schema", None) != "morpheus-pilot-retry-ledger-seal-v1":
        raise ValueError("unsupported retry ledger seal schema")
    if not isinstance(expected_operation, str) or not expected_operation.strip() or expected_operation != expected_operation.strip():
        raise ValueError("expected_operation must be canonical non-empty text")

    operation = getattr(seal, "operation", None)
    if operation != expected_operation:
        raise ValueError("retry ledger seal operation mismatch")

    key = _sha("key_sha256", getattr(seal, "key_sha256", None))
    request = _sha("request_sha256", getattr(seal, "request_sha256", None))
    expected_key = _sha("expected_key_sha256", expected_key_sha256)
    expected_request = _sha("expected_request_sha256", expected_request_sha256)
    if key != expected_key or request != expected_request:
        raise ValueError("retry ledger seal lineage mismatch")

    ledger = _sha("ledger_sha256", getattr(seal, "ledger_sha256", None))
    policy = _sha("policy_sha256", getattr(seal, "policy_sha256", None))
    seal_id = _sha("seal_sha256", getattr(seal, "seal_sha256", None))
    if len({key, request, ledger, policy, seal_id}) != 5:
        raise ValueError("retry ledger verification evidence identities must be independent")

    disposition = getattr(seal, "disposition", None)
    if disposition not in _ALLOWED:
        raise ValueError("unsupported retry ledger disposition")
    terminal = getattr(seal, "terminal", None)
    manual = getattr(seal, "manual_resolution_required", None)
    retry = getattr(seal, "retry_requires_new_authorization", None)
    if not all(isinstance(v, bool) for v in (terminal, manual, retry)):
        raise ValueError("retry ledger seal flags must be exact booleans")
    expected_state = {
        "COMPLETED": (True, False, False),
        "MANUAL_RESOLUTION": (True, True, False),
        "RETRY_PENDING": (False, False, True),
    }[disposition]
    if (terminal, manual, retry) != expected_state:
        raise ValueError("retry ledger disposition contradicts sealed state")

    sealed_at_utc = _canonical_utc("sealed_at_utc", getattr(seal, "sealed_at_utc", None))
    seal_payload = {
        "schema": "morpheus-pilot-retry-ledger-seal-v1",
        "operation": operation,
        "key_sha256": key,
        "request_sha256": request,
        "ledger_sha256": ledger,
        "policy_sha256": policy,
        "disposition": disposition,
        "sealed_at_utc": sealed_at_utc,
        "terminal": terminal,
        "manual_resolution_required": manual,
        "retry_requires_new_authorization": retry,
    }
    if _digest(seal_payload) != seal_id:
        raise ValueError("retry ledger seal digest mismatch")

    payload = {
        "schema": "morpheus-pilot-retry-ledger-seal-verification-v1",
        "operation": operation,
        "key_sha256": key,
        "request_sha256": request,
        "ledger_sha256": ledger,
        "policy_sha256": policy,
        "seal_sha256": seal_id,
        "disposition": disposition,
        "verified_at_utc": _utc(verified_at),
        "verified": True,
    }
    return PilotRetryLedgerSealVerification(**payload, verification_sha256=_digest(payload))
