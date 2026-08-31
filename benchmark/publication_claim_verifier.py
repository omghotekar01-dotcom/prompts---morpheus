"""Independent verifier for MORPHEUS publication-claim manifests."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


class PublicationClaimVerificationError(ValueError):
    pass


def _sha256(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _digest(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise PublicationClaimVerificationError(f"{name} must be a 64-character SHA-256 hex digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise PublicationClaimVerificationError(f"{name} must be hexadecimal") from exc
    return value.lower()


def verify_publication_claim_manifest(manifest: Mapping[str, Any]) -> str:
    """Recompute and verify an exported publication-claim manifest.

    Returns the canonical manifest digest when valid. This function deliberately
    accepts only plain serialized data so an independent lab need not trust the
    builder implementation or a Python dataclass instance from the producer.
    """
    if not isinstance(manifest, Mapping):
        raise PublicationClaimVerificationError("manifest must be a mapping")
    if manifest.get("publication_claims_authorized") is not True:
        raise PublicationClaimVerificationError("publication claims are not authorized")
    if manifest.get("production_deployment_authorized") is not False:
        raise PublicationClaimVerificationError("publication evidence must not authorize production deployment")

    revision = manifest.get("source_revision")
    if not isinstance(revision, str) or len(revision) != 40:
        raise PublicationClaimVerificationError("source_revision must be a full Git SHA")
    try:
        int(revision, 16)
    except ValueError as exc:
        raise PublicationClaimVerificationError("source_revision must be hexadecimal") from exc

    release_sha = _digest(manifest.get("consensus_release_sha256"), "consensus_release_sha256")
    artifacts = manifest.get("benchmark_artifacts")
    claims = manifest.get("claims")
    if not isinstance(artifacts, (list, tuple)) or not artifacts:
        raise PublicationClaimVerificationError("benchmark_artifacts must be non-empty")
    if not isinstance(claims, (list, tuple)) or not claims:
        raise PublicationClaimVerificationError("claims must be non-empty")

    canonical_artifacts: list[list[str]] = []
    names: set[str] = set()
    digests: set[str] = {release_sha}
    for item in artifacts:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise PublicationClaimVerificationError("each benchmark artifact must be [name, sha256]")
        name, raw_digest = item
        if not isinstance(name, str) or not name.strip():
            raise PublicationClaimVerificationError("artifact name must be non-empty")
        name = name.strip()
        digest = _digest(raw_digest, f"artifact {name}")
        if name in names or digest in digests:
            raise PublicationClaimVerificationError("publication evidence must be unique and non-aliased")
        names.add(name)
        digests.add(digest)
        canonical_artifacts.append([name, digest])

    canonical_claims: list[str] = []
    seen_claims: set[str] = set()
    for claim in claims:
        if not isinstance(claim, str) or not claim.strip():
            raise PublicationClaimVerificationError("every claim must be non-empty")
        normalized = " ".join(claim.split())
        if normalized in seen_claims:
            raise PublicationClaimVerificationError("claims must be unique")
        seen_claims.add(normalized)
        canonical_claims.append(normalized)

    payload = {
        "schema": "morpheus.publication_claim_manifest.v1",
        "source_revision": revision.lower(),
        "consensus_release_sha256": release_sha,
        "benchmark_artifacts": sorted(canonical_artifacts),
        "claims": sorted(canonical_claims),
        "publication_claims_authorized": True,
        "production_deployment_authorized": False,
    }
    expected = _sha256(payload)
    supplied = _digest(manifest.get("manifest_sha256"), "manifest_sha256")
    if supplied != expected:
        raise PublicationClaimVerificationError("manifest digest mismatch")
    return expected
