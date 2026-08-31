"""Deterministic cross-manifest catalog for independently verified publication claims.

The catalog is intentionally downstream of ``publication_claim_verifier``.  It lets an
external reviewer combine several valid claim manifests while preventing revision mixing,
duplicate manifests, duplicate human-readable claims, and accidental production authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Sequence

from .publication_claim_verifier import verify_publication_claim_manifest


class PublicationClaimCatalogError(ValueError):
    pass


@dataclass(frozen=True)
class PublicationClaimCatalog:
    source_revision: str
    manifest_count: int
    claim_count: int
    manifest_sha256: tuple[str, ...]
    claims: tuple[str, ...]
    catalog_sha256: str
    publication_claims_authorized: bool = True
    production_deployment_authorized: bool = False


def _canonical_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_publication_claim_catalog(manifests: Sequence[Mapping[str, Any]]) -> PublicationClaimCatalog:
    """Combine independently verifiable manifests belonging to one exact source revision."""
    if isinstance(manifests, (str, bytes)) or not manifests:
        raise PublicationClaimCatalogError("at least one manifest is required")

    revisions: set[str] = set()
    manifest_digests: list[str] = []
    claims: list[str] = []

    for manifest in manifests:
        if not isinstance(manifest, Mapping):
            raise PublicationClaimCatalogError("each manifest must be a mapping")
        try:
            digest = verify_publication_claim_manifest(manifest)
        except ValueError as exc:
            raise PublicationClaimCatalogError(f"invalid publication manifest: {exc}") from exc

        revision = manifest.get("source_revision")
        if not isinstance(revision, str):
            raise PublicationClaimCatalogError("source_revision must be a string")
        revisions.add(revision.lower())
        manifest_digests.append(digest.lower())

        manifest_claims = manifest.get("claims")
        if not isinstance(manifest_claims, list) or not manifest_claims:
            raise PublicationClaimCatalogError("each manifest must contain claims")
        for claim in manifest_claims:
            if not isinstance(claim, str) or not claim.strip():
                raise PublicationClaimCatalogError("claims must be non-empty strings")
            claims.append(claim.strip())

    if len(revisions) != 1:
        raise PublicationClaimCatalogError("publication manifests must target one source revision")
    if len(set(manifest_digests)) != len(manifest_digests):
        raise PublicationClaimCatalogError("duplicate publication manifests are not independent catalog entries")

    normalized_claims = [claim.casefold() for claim in claims]
    if len(set(normalized_claims)) != len(normalized_claims):
        raise PublicationClaimCatalogError("duplicate publication claims are not allowed across manifests")

    revision = next(iter(revisions))
    ordered_digests = tuple(sorted(manifest_digests))
    ordered_claims = tuple(sorted(claims, key=lambda value: value.casefold()))
    payload = {
        "schema": "morpheus.publication_claim_catalog.v1",
        "source_revision": revision,
        "manifest_sha256": list(ordered_digests),
        "claims": list(ordered_claims),
        "publication_claims_authorized": True,
        "production_deployment_authorized": False,
    }
    return PublicationClaimCatalog(
        source_revision=revision,
        manifest_count=len(ordered_digests),
        claim_count=len(ordered_claims),
        manifest_sha256=ordered_digests,
        claims=ordered_claims,
        catalog_sha256=_canonical_digest(payload),
    )
