from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_PURPOSES = {
    "archive_publication",
    "benchmark_claim",
    "migration_recommendation",
    "research_summary",
}


@dataclass(frozen=True)
class MigrationReproductionConsumption:
    schema: str
    attestation_sha256: str
    release_manifest_sha256: str
    reproduction_campaign_sha256: str
    purpose: str
    consumer_artifact_sha256: str
    active_revocation_sha256s: tuple[str, ...]
    reproduction_authorized: bool
    consumption_sha256: str


def _hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value) or value == "0" * 64:
        raise ValueError(f"{field} must be a non-placeholder lowercase SHA-256 identity")
    return value


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def authorize_generated_migration_reproduction_consumption(
    *,
    attestation: Any,
    revocations: Sequence[Any],
    purpose: str,
    consumer_artifact_sha256: str,
) -> MigrationReproductionConsumption:
    if getattr(attestation, "reproduction_verified", None) is not True:
        raise ValueError("attestation must be explicitly reproduction-verified")
    attestation_id = _hash(getattr(attestation, "attestation_sha256", None), "attestation.attestation_sha256")
    release_id = _hash(getattr(attestation, "release_manifest_sha256", None), "attestation.release_manifest_sha256")
    campaign_id = _hash(getattr(attestation, "reproduction_campaign_sha256", None), "attestation.reproduction_campaign_sha256")
    consumer_id = _hash(consumer_artifact_sha256, "consumer_artifact_sha256")
    if purpose not in _ALLOWED_PURPOSES:
        raise ValueError("unsupported reproduction consumption purpose")

    identities = [attestation_id, release_id, campaign_id, consumer_id]
    if len(set(identities)) != len(identities):
        raise ValueError("consumption identities must be independent")

    active: list[str] = []
    seen_revocations: set[str] = set()
    for revocation in revocations:
        if getattr(revocation, "revoked", None) is not True:
            raise ValueError("revocation entries must be explicitly revoked")
        revocation_id = _hash(getattr(revocation, "revocation_sha256", None), "revocation.revocation_sha256")
        target_id = _hash(getattr(revocation, "attestation_sha256", None), "revocation.attestation_sha256")
        if revocation_id in seen_revocations:
            raise ValueError("revocation identities must be unique")
        seen_revocations.add(revocation_id)
        if revocation_id in identities:
            raise ValueError("revocation and consumption identities must be independent")
        if target_id == attestation_id:
            active.append(revocation_id)

    active_revocations = tuple(sorted(active))
    if active_revocations:
        raise ValueError("reproduction attestation has an active revocation")

    payload = {
        "schema": "morpheus.generated_migration_reproduction_consumption.v1",
        "attestation_sha256": attestation_id,
        "release_manifest_sha256": release_id,
        "reproduction_campaign_sha256": campaign_id,
        "purpose": purpose,
        "consumer_artifact_sha256": consumer_id,
        "active_revocation_sha256s": active_revocations,
        "reproduction_authorized": True,
    }
    return MigrationReproductionConsumption(**payload, consumption_sha256=_canonical_sha256(payload))
