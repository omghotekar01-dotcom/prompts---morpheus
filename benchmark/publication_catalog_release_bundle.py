"""Deterministic release bundle for independently verified publication catalogs.

This layer packages a publication catalog for external handoff without granting
runtime or production authority.  It is intentionally dependency-free so an
external verifier can reproduce the digest with only the Python standard
library.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Iterable, Mapping, Any

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{7,40}$")
SCHEMA = "morpheus.publication_catalog_release.v1"


def _canonical(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def _require_hash(value: str, name: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
    return value


def _require_git_sha(value: str) -> str:
    if not isinstance(value, str) or not _GIT_SHA.fullmatch(value):
        raise ValueError("source_revision must be a lowercase git revision")
    return value


@dataclass(frozen=True)
class PublicationCatalogReleaseBundle:
    source_revision: str
    catalog_digest: str
    verifier_digest: str
    manifest_digests: tuple[str, ...]
    claim_count: int
    release_digest: str
    schema: str = SCHEMA
    production_deployment_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "source_revision": self.source_revision,
            "catalog_digest": self.catalog_digest,
            "verifier_digest": self.verifier_digest,
            "manifest_digests": list(self.manifest_digests),
            "claim_count": self.claim_count,
            "production_deployment_authorized": self.production_deployment_authorized,
            "release_digest": self.release_digest,
        }


def build_release_bundle(*, source_revision: str, catalog_digest: str,
                         verifier_digest: str, manifest_digests: Iterable[str],
                         claim_count: int) -> PublicationCatalogReleaseBundle:
    revision = _require_git_sha(source_revision)
    catalog = _require_hash(catalog_digest, "catalog_digest")
    verifier = _require_hash(verifier_digest, "verifier_digest")
    manifests = tuple(sorted(_require_hash(v, "manifest_digest") for v in manifest_digests))
    if len(manifests) < 2:
        raise ValueError("at least two independently verified manifests are required")
    if len(set(manifests)) != len(manifests):
        raise ValueError("manifest digests must be unique")
    if isinstance(claim_count, bool) or not isinstance(claim_count, int) or claim_count < 1:
        raise ValueError("claim_count must be a positive integer")

    payload = {
        "schema": SCHEMA,
        "source_revision": revision,
        "catalog_digest": catalog,
        "verifier_digest": verifier,
        "manifest_digests": list(manifests),
        "claim_count": claim_count,
        "production_deployment_authorized": False,
    }
    digest = sha256(_canonical(payload)).hexdigest()
    return PublicationCatalogReleaseBundle(
        source_revision=revision,
        catalog_digest=catalog,
        verifier_digest=verifier,
        manifest_digests=manifests,
        claim_count=claim_count,
        release_digest=digest,
    )


def verify_release_bundle(raw: Mapping[str, Any]) -> PublicationCatalogReleaseBundle:
    expected = {
        "schema", "source_revision", "catalog_digest", "verifier_digest",
        "manifest_digests", "claim_count", "production_deployment_authorized",
        "release_digest",
    }
    if set(raw) != expected:
        raise ValueError("release bundle must use the closed v1 schema")
    if raw.get("schema") != SCHEMA:
        raise ValueError("unsupported release bundle schema")
    if raw.get("production_deployment_authorized") is not False:
        raise ValueError("publication evidence cannot authorize production deployment")
    rebuilt = build_release_bundle(
        source_revision=raw["source_revision"],
        catalog_digest=raw["catalog_digest"],
        verifier_digest=raw["verifier_digest"],
        manifest_digests=raw["manifest_digests"],
        claim_count=raw["claim_count"],
    )
    if not isinstance(raw["release_digest"], str) or raw["release_digest"] != rebuilt.release_digest:
        raise ValueError("release bundle digest mismatch")
    return rebuilt
