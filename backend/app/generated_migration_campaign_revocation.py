from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_REASONS = {
    "benchmark_source_retracted",
    "manifest_artifact_invalidated",
    "measurement_protocol_violation",
    "toolchain_identity_invalidated",
    "report_tampering_detected",
    "experimental_design_invalidated",
}


@dataclass(frozen=True)
class MigrationCampaignRevocation:
    revoked: bool
    campaign_decision_sha256: str
    reason: str
    evidence_sha256: tuple[str, ...]
    predecessor_revocation_sha256: str | None
    revocation_sha256: str


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value) or value == "0" * 64:
        raise ValueError(f"{field} must be a non-placeholder lowercase SHA-256 identity")
    return value


def revoke_generated_migration_campaign(
    *,
    campaign_decision_sha256: str,
    reason: str,
    evidence_sha256: Sequence[str],
    predecessor_revocation_sha256: str | None = None,
) -> MigrationCampaignRevocation:
    """Append-only revocation for previously promoted generated-migration evidence.

    Revocation never rewrites or deletes the historical promotion decision. Instead it
    creates an independently hash-bound record that downstream claim gates can consume.
    Evidence identities must be independent of the campaign decision and of the optional
    predecessor record, preventing self-referential or circular revocation chains.
    """
    campaign = _require_sha256(campaign_decision_sha256, "campaign_decision_sha256")

    if not isinstance(reason, str) or reason not in _ALLOWED_REASONS:
        raise ValueError("reason is not an allowed generated-migration revocation reason")

    if not isinstance(evidence_sha256, Sequence) or isinstance(evidence_sha256, (str, bytes, bytearray)):
        raise ValueError("evidence_sha256 must be a sequence")
    if not evidence_sha256:
        raise ValueError("at least one independent revocation evidence identity is required")

    normalized: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(evidence_sha256):
        digest = _require_sha256(value, f"evidence_sha256[{index}]")
        if digest == campaign:
            raise ValueError("revocation evidence must not alias the campaign decision")
        if digest in seen:
            raise ValueError("duplicate revocation evidence identity")
        seen.add(digest)
        normalized.append(digest)

    predecessor: str | None = None
    if predecessor_revocation_sha256 is not None:
        predecessor = _require_sha256(predecessor_revocation_sha256, "predecessor_revocation_sha256")
        if predecessor == campaign:
            raise ValueError("predecessor revocation must not alias the campaign decision")
        if predecessor in seen:
            raise ValueError("predecessor revocation must be independent of current evidence")

    payload = {
        "schema": "morpheus.generated_migration_campaign_revocation.v1",
        "revoked": True,
        "campaign_decision_sha256": campaign,
        "reason": reason,
        "evidence_sha256": sorted(normalized),
        "predecessor_revocation_sha256": predecessor,
    }
    revocation_sha256 = _canonical_sha256(payload)

    if revocation_sha256 == campaign or revocation_sha256 in seen or revocation_sha256 == predecessor:
        raise ValueError("revocation identity must be independent of all upstream identities")

    return MigrationCampaignRevocation(
        revoked=True,
        campaign_decision_sha256=campaign,
        reason=reason,
        evidence_sha256=tuple(payload["evidence_sha256"]),
        predecessor_revocation_sha256=predecessor,
        revocation_sha256=revocation_sha256,
    )
