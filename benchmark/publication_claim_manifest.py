"""Claim-level publication manifest for independently reproduced MORPHEUS results.

The consensus release says evidence may support publication. This module narrows that
permission to an explicit set of human-readable claims and exact benchmark artifacts,
so a paper, poster, README, or demo cannot silently broaden the verified result.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Sequence


class PublicationClaimError(ValueError):
    pass


PUBLICATION_CLAIM_MANIFEST_SCHEMA = "morpheus.publication_claim_manifest.v1"


def _sha256(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _digest(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise PublicationClaimError(f"{name} must be a 64-character SHA-256 hex digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise PublicationClaimError(f"{name} must be hexadecimal") from exc
    return value.lower()


def _claims(values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise PublicationClaimError("claims must be a sequence of strings")
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise PublicationClaimError("every claim must be a non-empty string")
        claim = " ".join(value.split())
        if len(claim) > 500:
            raise PublicationClaimError("claim exceeds 500 characters")
        normalized.append(claim)
    if not normalized:
        raise PublicationClaimError("at least one claim is required")
    if len(set(normalized)) != len(normalized):
        raise PublicationClaimError("claims must be unique")
    return tuple(sorted(normalized))


@dataclass(frozen=True)
class PublicationClaimManifest:
    schema: str
    source_revision: str
    consensus_release_sha256: str
    benchmark_artifacts: tuple[tuple[str, str], ...]
    claims: tuple[str, ...]
    publication_claims_authorized: bool
    production_deployment_authorized: bool
    manifest_sha256: str


def build_publication_claim_manifest(
    release: Mapping[str, Any], *, claims: Sequence[str], benchmark_artifacts: Mapping[str, str]
) -> PublicationClaimManifest:
    """Bind publishable wording to the exact reproduced benchmark evidence.

    The input release must itself authorize publication and must explicitly deny
    production-deployment authority. Artifact names and digests are canonicalized,
    sorted, and bound into the manifest digest.
    """
    if release.get("publication_claims_authorized") is not True:
        raise PublicationClaimError("consensus release does not authorize publication claims")
    if release.get("production_deployment_authorized") is not False:
        raise PublicationClaimError("publication release must not carry production authority")

    source_revision = release.get("source_revision")
    if not isinstance(source_revision, str) or len(source_revision) != 40:
        raise PublicationClaimError("source_revision must be a full 40-character Git revision")
    try:
        int(source_revision, 16)
    except ValueError as exc:
        raise PublicationClaimError("source_revision must be hexadecimal") from exc

    release_sha = _digest(release.get("release_sha256"), "release_sha256")
    if not isinstance(benchmark_artifacts, Mapping) or not benchmark_artifacts:
        raise PublicationClaimError("benchmark_artifacts must be a non-empty mapping")

    artifacts: list[tuple[str, str]] = []
    seen_digests: set[str] = {release_sha}
    for raw_name, raw_digest in benchmark_artifacts.items():
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise PublicationClaimError("artifact names must be non-empty strings")
        name = raw_name.strip()
        digest = _digest(raw_digest, f"benchmark_artifacts[{name!r}]")
        if digest in seen_digests:
            raise PublicationClaimError("publication evidence must not alias")
        seen_digests.add(digest)
        artifacts.append((name, digest))
    if len({name for name, _ in artifacts}) != len(artifacts):
        raise PublicationClaimError("artifact names must be unique")

    canonical_claims = _claims(claims)
    canonical_artifacts = tuple(sorted(artifacts))
    payload = {
        "schema": PUBLICATION_CLAIM_MANIFEST_SCHEMA,
        "source_revision": source_revision.lower(),
        "consensus_release_sha256": release_sha,
        "benchmark_artifacts": [list(item) for item in canonical_artifacts],
        "claims": list(canonical_claims),
        "publication_claims_authorized": True,
        "production_deployment_authorized": False,
    }
    return PublicationClaimManifest(
        schema=PUBLICATION_CLAIM_MANIFEST_SCHEMA,
        source_revision=payload["source_revision"],
        consensus_release_sha256=release_sha,
        benchmark_artifacts=canonical_artifacts,
        claims=canonical_claims,
        publication_claims_authorized=True,
        production_deployment_authorized=False,
        manifest_sha256=_sha256(payload),
    )
