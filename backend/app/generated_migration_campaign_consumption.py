from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_CAPABILITIES = {
    "publication_claim",
    "candidate_comparison",
    "migration_recommendation",
    "research_summary",
}


@dataclass(frozen=True)
class MigrationCampaignConsumption:
    authorized: bool
    capability: str
    campaign_decision_sha256: str
    active_revocation_sha256: tuple[str, ...]
    consumption_sha256: str


def _require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value) or value == "0" * 64:
        raise ValueError(f"{field} must be a non-placeholder lowercase SHA-256 identity")
    return value


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def consume_generated_migration_campaign(
    *,
    campaign_decision_sha256: str,
    promoted: bool,
    capability: str,
    revocations: Sequence[Mapping[str, Any]] = (),
) -> MigrationCampaignConsumption:
    """Authorize downstream use only for a promoted, currently unrevoked campaign.

    This is intentionally fail-closed: promotion is historical evidence, while current
    authority additionally depends on the absence of a valid revocation targeting that
    exact decision. A revocation for another campaign cannot contaminate this decision.
    """
    campaign = _require_sha256(campaign_decision_sha256, "campaign_decision_sha256")
    if promoted is not True:
        raise ValueError("campaign must be explicitly promoted")
    if not isinstance(capability, str) or capability not in _ALLOWED_CAPABILITIES:
        raise ValueError("capability is not an allowed generated-migration consumer")
    if not isinstance(revocations, Sequence) or isinstance(revocations, (str, bytes, bytearray)):
        raise ValueError("revocations must be a sequence")

    active: list[str] = []
    seen: set[str] = set()
    for index, revocation in enumerate(revocations):
        if not isinstance(revocation, Mapping):
            raise ValueError(f"revocations[{index}] must be an object")
        revoked = revocation.get("revoked")
        if revoked is not True:
            if revoked is False:
                continue
            raise ValueError("revoked must be an exact boolean")
        target = _require_sha256(revocation.get("campaign_decision_sha256"), f"revocations[{index}].campaign_decision_sha256")
        digest = _require_sha256(revocation.get("revocation_sha256"), f"revocations[{index}].revocation_sha256")
        if digest in seen:
            raise ValueError("duplicate revocation identity")
        seen.add(digest)
        if target == campaign:
            active.append(digest)

    if active:
        raise ValueError("generated-migration campaign has an active revocation")

    payload = {
        "schema": "morpheus.generated_migration_campaign_consumption.v1",
        "authorized": True,
        "capability": capability,
        "campaign_decision_sha256": campaign,
        "active_revocation_sha256": [],
    }
    return MigrationCampaignConsumption(
        authorized=True,
        capability=capability,
        campaign_decision_sha256=campaign,
        active_revocation_sha256=(),
        consumption_sha256=_canonical_sha256(payload),
    )
