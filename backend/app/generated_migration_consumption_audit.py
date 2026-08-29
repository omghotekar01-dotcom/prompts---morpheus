from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_CAPABILITIES = {
    "publication_claim",
    "candidate_comparison",
    "migration_recommendation",
    "research_summary",
}


@dataclass(frozen=True)
class MigrationConsumptionAudit:
    schema: str
    sequence: int
    capability: str
    campaign_decision_sha256: str
    consumption_sha256: str
    predecessor_audit_sha256: str | None
    audit_sha256: str


def _require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value) or value == "0" * 64:
        raise ValueError(f"{field} must be a non-placeholder lowercase SHA-256 identity")
    return value


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def create_migration_consumption_audit(
    *,
    sequence: int,
    capability: str,
    campaign_decision_sha256: str,
    consumption_sha256: str,
    authorized: bool,
    predecessor_audit_sha256: str | None = None,
) -> MigrationConsumptionAudit:
    """Create one deterministic append-only audit record for an authorized consumption.

    The function deliberately does not accept user/device identity or free-form notes.
    Research authority is represented only by content-addressed evidence and a strict
    predecessor chain, which keeps the ledger deterministic and privacy-minimal.
    """
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        raise ValueError("sequence must be a non-negative exact integer")
    if not isinstance(capability, str) or capability not in _ALLOWED_CAPABILITIES:
        raise ValueError("capability is not an allowed generated-migration consumer")
    if authorized is not True:
        raise ValueError("only explicitly authorized consumption may enter the audit chain")

    campaign = _require_sha256(campaign_decision_sha256, "campaign_decision_sha256")
    consumption = _require_sha256(consumption_sha256, "consumption_sha256")
    if consumption == campaign:
        raise ValueError("consumption identity must be independent from campaign decision")

    predecessor: str | None
    if sequence == 0:
        if predecessor_audit_sha256 is not None:
            raise ValueError("genesis audit record must not have a predecessor")
        predecessor = None
    else:
        predecessor = _require_sha256(predecessor_audit_sha256, "predecessor_audit_sha256")
        if predecessor in {campaign, consumption}:
            raise ValueError("predecessor identity must be independent from current evidence")

    payload = {
        "schema": "morpheus.generated_migration_consumption_audit.v1",
        "sequence": sequence,
        "capability": capability,
        "campaign_decision_sha256": campaign,
        "consumption_sha256": consumption,
        "predecessor_audit_sha256": predecessor,
    }
    audit = _canonical_sha256(payload)
    if audit in {campaign, consumption, predecessor}:
        raise ValueError("derived audit identity aliases upstream evidence")

    return MigrationConsumptionAudit(
        schema=payload["schema"],
        sequence=sequence,
        capability=capability,
        campaign_decision_sha256=campaign,
        consumption_sha256=consumption,
        predecessor_audit_sha256=predecessor,
        audit_sha256=audit,
    )
