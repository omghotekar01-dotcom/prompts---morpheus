from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class MigrationReproductionAttestation:
    schema: str
    release_manifest_sha256: str
    reproduction_campaign_sha256: str
    publication_bundle_sha256: str
    archive_artifact_sha256: str
    attestation_policy_sha256: str
    reproduction_verified: bool
    attestation_sha256: str


def _hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value) or value == "0" * 64:
        raise ValueError(f"{field} must be a non-placeholder lowercase SHA-256 identity")
    return value


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def attest_generated_migration_reproduction(*, campaign: Any, publication_bundle_sha256: str, archive_artifact_sha256: str, attestation_policy_sha256: str) -> MigrationReproductionAttestation:
    if getattr(campaign, "reproduction_campaign_verified", None) is not True:
        raise ValueError("campaign must be explicitly reproduction-verified")
    release = _hash(getattr(campaign, "release_manifest_sha256", None), "campaign.release_manifest_sha256")
    campaign_id = _hash(getattr(campaign, "campaign_sha256", None), "campaign.campaign_sha256")
    publication = _hash(publication_bundle_sha256, "publication_bundle_sha256")
    archive = _hash(archive_artifact_sha256, "archive_artifact_sha256")
    policy = _hash(attestation_policy_sha256, "attestation_policy_sha256")
    identities = [release, campaign_id, publication, archive, policy]
    if len(set(identities)) != len(identities):
        raise ValueError("attestation identities must be independent")
    payload = {
        "schema": "morpheus.generated_migration_reproduction_attestation.v1",
        "release_manifest_sha256": release,
        "reproduction_campaign_sha256": campaign_id,
        "publication_bundle_sha256": publication,
        "archive_artifact_sha256": archive,
        "attestation_policy_sha256": policy,
        "reproduction_verified": True,
    }
    return MigrationReproductionAttestation(**payload, attestation_sha256=_canonical_sha256(payload))
