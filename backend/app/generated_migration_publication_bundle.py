from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CLAIM_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ALLOWED_CAPABILITIES = {"publication_claim", "research_summary"}


@dataclass(frozen=True)
class MigrationPublicationBundle:
    schema: str
    claim_id: str
    campaign_decision_sha256: str
    consumption_sha256: str
    consumption_audit_sha256: str
    report_sha256: tuple[str, ...]
    source_artifact_sha256: tuple[str, ...]
    revocation_snapshot_sha256: str
    publication_ready: bool
    bundle_sha256: str


def _hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value) or value == "0" * 64:
        raise ValueError(f"{field} must be a non-placeholder lowercase SHA-256 identity")
    return value


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_generated_migration_publication_bundle(
    *,
    claim_id: str,
    capability: str,
    campaign_decision_sha256: str,
    consumption_sha256: str,
    consumption_audit_sha256: str,
    report_sha256: Sequence[str],
    source_artifact_sha256: Sequence[str],
    revocation_snapshot_sha256: str,
    consumption_authorized: bool,
    active_revocation_count: int,
) -> MigrationPublicationBundle:
    """Create a reproducible evidence package for a currently authorized research claim."""
    if not isinstance(claim_id, str) or not _CLAIM_ID.fullmatch(claim_id):
        raise ValueError("claim_id must be a canonical 1-128 character identifier")
    if not isinstance(capability, str) or capability not in _ALLOWED_CAPABILITIES:
        raise ValueError("capability is not publication-compatible")
    if consumption_authorized is not True:
        raise ValueError("consumption must be explicitly authorized")
    if isinstance(active_revocation_count, bool) or not isinstance(active_revocation_count, int) or active_revocation_count < 0:
        raise ValueError("active_revocation_count must be a non-negative exact integer")
    if active_revocation_count != 0:
        raise ValueError("publication evidence cannot contain an active campaign revocation")

    campaign = _hash(campaign_decision_sha256, "campaign_decision_sha256")
    consumption = _hash(consumption_sha256, "consumption_sha256")
    audit = _hash(consumption_audit_sha256, "consumption_audit_sha256")
    revocation_snapshot = _hash(revocation_snapshot_sha256, "revocation_snapshot_sha256")

    if not isinstance(report_sha256, Sequence) or isinstance(report_sha256, (str, bytes, bytearray)):
        raise ValueError("report_sha256 must be a sequence")
    reports = tuple(sorted(_hash(value, "report_sha256[]") for value in report_sha256))
    if len(reports) < 3:
        raise ValueError("publication requires at least three campaign report identities")
    if len(set(reports)) != len(reports):
        raise ValueError("duplicate report evidence identity")

    if not isinstance(source_artifact_sha256, Sequence) or isinstance(source_artifact_sha256, (str, bytes, bytearray)):
        raise ValueError("source_artifact_sha256 must be a sequence")
    source_artifacts = tuple(sorted(_hash(value, "source_artifact_sha256[]") for value in source_artifact_sha256))
    if not source_artifacts:
        raise ValueError("publication requires source artifact evidence")
    if len(set(source_artifacts)) != len(source_artifacts):
        raise ValueError("duplicate source artifact identity")

    top_level = [campaign, consumption, audit, revocation_snapshot]
    if len(set(top_level)) != len(top_level):
        raise ValueError("top-level publication evidence identities must be independent")
    if set(reports) & set(top_level):
        raise ValueError("report evidence must be independent from top-level evidence")
    if set(source_artifacts) & (set(top_level) | set(reports)):
        raise ValueError("source artifact evidence must be independent from other publication evidence")

    payload = {
        "schema": "morpheus.generated_migration_publication_bundle.v1",
        "claim_id": claim_id,
        "capability": capability,
        "campaign_decision_sha256": campaign,
        "consumption_sha256": consumption,
        "consumption_audit_sha256": audit,
        "report_sha256": list(reports),
        "source_artifact_sha256": list(source_artifacts),
        "revocation_snapshot_sha256": revocation_snapshot,
        "active_revocation_count": 0,
        "publication_ready": True,
    }
    return MigrationPublicationBundle(
        schema=payload["schema"],
        claim_id=claim_id,
        campaign_decision_sha256=campaign,
        consumption_sha256=consumption,
        consumption_audit_sha256=audit,
        report_sha256=reports,
        source_artifact_sha256=source_artifacts,
        revocation_snapshot_sha256=revocation_snapshot,
        publication_ready=True,
        bundle_sha256=_canonical_sha256(payload),
    )
