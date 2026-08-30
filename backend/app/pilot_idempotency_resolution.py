from __future__ import annotations

import hashlib
import re
from typing import Any

from .idempotency import IdempotencyJournal
from .storage import StateStore


_OUTCOMES = {"CONFIRMED_NO_SIDE_EFFECT", "CONFIRMED_SIDE_EFFECT_PRESENT"}
_OPERATOR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@-]{2,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _require_sha(value: str, name: str) -> str:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 identity")
    return value


def _reason_sha256(reason: str) -> str:
    normalized = reason.strip()
    if len(normalized) < 12 or len(normalized) > 2000:
        raise ValueError("resolution reason must contain 12-2000 characters")
    if any(ord(ch) < 32 and ch not in {"\t", "\n"} for ch in normalized):
        raise ValueError("resolution reason contains unsupported control characters")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def resolve_idempotency_ambiguity(
    *,
    store: StateStore,
    journal: IdempotencyJournal,
    operation: str,
    key_sha256: str,
    request_sha256: str,
    outcome: str,
    operator_id: str,
    reason: str,
) -> dict[str, Any]:
    """Apply one manual ambiguity resolution behind hash-chained audit evidence.

    The reason text is never persisted by this workflow; only its SHA-256 is
    written to the evidence ledger and journal. This avoids turning an incident
    note into a new secret-bearing data store.
    """

    operation = operation.strip()
    if not operation or len(operation) > 128:
        raise ValueError("operation must contain 1-128 characters")
    _require_sha(key_sha256, "key_sha256")
    _require_sha(request_sha256, "request_sha256")
    if outcome not in _OUTCOMES:
        raise ValueError(f"outcome must be one of {sorted(_OUTCOMES)}")
    if not _OPERATOR_RE.fullmatch(operator_id):
        raise ValueError("operator_id must be a canonical 3-128 character identity")
    reason_sha256 = _reason_sha256(reason)

    matches = [
        item
        for item in journal.list_unresolved_ambiguities(limit=500)
        if item["operation"] == operation
        and item["key_sha256"] == key_sha256
        and item["request_sha256"] == request_sha256
    ]
    if len(matches) != 1:
        raise ValueError("resolution target is not exactly one unresolved ambiguous idempotency record")

    subject = f"{operation}:{key_sha256}"
    authorization = store.append_evidence(
        kind="idempotency_operator_resolution_authorized",
        subject=subject,
        payload={
            "operation": operation,
            "key_sha256": key_sha256,
            "request_sha256": request_sha256,
            "outcome": outcome,
            "operator_id": operator_id,
            "reason_sha256": reason_sha256,
            "evidence_state": "MANUAL_IDEMPOTENCY_RESOLUTION_AUTHORIZATION_RECORDED",
            "truth_boundary": "The reason text is not persisted; this entry records only its byte identity and the operator's declared resolution.",
        },
    )

    if outcome == "CONFIRMED_SIDE_EFFECT_PRESENT":
        journal.resolve_confirmed_side_effect_present(
            operation=operation,
            key_sha256=key_sha256,
            request_digest=request_sha256,
            reason_sha256=reason_sha256,
        )
        resulting_state = "RESOLVED_SIDE_EFFECT_PRESENT"
        retry_allowed = False
    else:
        journal.resolve_confirmed_no_side_effect(
            operation=operation,
            key_sha256=key_sha256,
            request_digest=request_sha256,
        )
        resulting_state = "REMOVED_AFTER_CONFIRMED_NO_SIDE_EFFECT"
        retry_allowed = True

    applied = store.append_evidence(
        kind="idempotency_operator_resolution_applied",
        subject=subject,
        payload={
            "operation": operation,
            "key_sha256": key_sha256,
            "request_sha256": request_sha256,
            "outcome": outcome,
            "operator_id": operator_id,
            "reason_sha256": reason_sha256,
            "authorization_entry_hash": authorization["entry_hash"],
            "resulting_state": resulting_state,
            "retry_allowed": retry_allowed,
            "evidence_state": "MANUAL_IDEMPOTENCY_RESOLUTION_APPLIED",
        },
    )

    return {
        "schema": "morpheus-idempotency-operator-resolution-v1",
        "operation": operation,
        "key_sha256": key_sha256,
        "request_sha256": request_sha256,
        "outcome": outcome,
        "operator_id": operator_id,
        "reason_sha256": reason_sha256,
        "resulting_state": resulting_state,
        "retry_allowed": retry_allowed,
        "authorization_evidence_hash": authorization["entry_hash"],
        "applied_evidence_hash": applied["entry_hash"],
        "truth_boundaries": [
            "This is a manual operator assertion after external/state inspection; MORPHEUS does not infer whether the ambiguous side effect occurred.",
            "CONFIRMED_NO_SIDE_EFFECT permits an explicit future retry but does not trigger one automatically.",
            "CONFIRMED_SIDE_EFFECT_PRESENT permanently blocks automatic retry for the original key and does not manufacture a replay response.",
        ],
    }
