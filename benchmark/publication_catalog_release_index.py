"""Deterministic index for independently verified MORPHEUS release bundles.

The index is a closed-world handoff artifact: it proves that a set of release
bundles all target one source revision, are individually valid, and are not
replayed under duplicate release identities. It grants no runtime or production
authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping

from benchmark.publication_catalog_release_bundle import verify_release_bundle

SCHEMA = "morpheus.publication_catalog_release_index.v1"


def _canonical(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


@dataclass(frozen=True)
class PublicationCatalogReleaseIndex:
    source_revision: str
    release_digests: tuple[str, ...]
    total_claim_count: int
    index_digest: str
    schema: str = SCHEMA
    production_deployment_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "source_revision": self.source_revision,
            "release_digests": list(self.release_digests),
            "total_claim_count": self.total_claim_count,
            "production_deployment_authorized": self.production_deployment_authorized,
            "index_digest": self.index_digest,
        }


def build_release_index(bundles: Iterable[Mapping[str, Any]]) -> PublicationCatalogReleaseIndex:
    verified = tuple(verify_release_bundle(bundle) for bundle in bundles)
    if len(verified) < 2:
        raise ValueError("at least two verified release bundles are required")

    source_revision = verified[0].source_revision
    if any(bundle.source_revision != source_revision for bundle in verified[1:]):
        raise ValueError("all release bundles must target the same source revision")

    release_digests = tuple(sorted(bundle.release_digest for bundle in verified))
    if len(set(release_digests)) != len(release_digests):
        raise ValueError("release bundle identities must be unique")

    total_claim_count = sum(bundle.claim_count for bundle in verified)
    payload = {
        "schema": SCHEMA,
        "source_revision": source_revision,
        "release_digests": list(release_digests),
        "total_claim_count": total_claim_count,
        "production_deployment_authorized": False,
    }
    index_digest = sha256(_canonical(payload)).hexdigest()
    return PublicationCatalogReleaseIndex(
        source_revision=source_revision,
        release_digests=release_digests,
        total_claim_count=total_claim_count,
        index_digest=index_digest,
    )


def verify_release_index(raw: Mapping[str, Any]) -> PublicationCatalogReleaseIndex:
    expected = {
        "schema",
        "source_revision",
        "release_digests",
        "total_claim_count",
        "production_deployment_authorized",
        "index_digest",
    }
    if set(raw) != expected:
        raise ValueError("release index must use the closed v1 schema")
    if raw.get("schema") != SCHEMA:
        raise ValueError("unsupported release index schema")
    if raw.get("production_deployment_authorized") is not False:
        raise ValueError("publication evidence cannot authorize production deployment")
    if isinstance(raw.get("total_claim_count"), bool) or not isinstance(raw.get("total_claim_count"), int) or raw["total_claim_count"] < 2:
        raise ValueError("total_claim_count must be an integer of at least two")

    releases = raw.get("release_digests")
    if not isinstance(releases, list) or len(releases) < 2:
        raise ValueError("release_digests must contain at least two identities")
    if releases != sorted(releases) or len(set(releases)) != len(releases):
        raise ValueError("release_digests must be unique and canonical-order sorted")
    if any(not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value) for value in releases):
        raise ValueError("release_digests must be lowercase SHA-256 hex digests")

    payload = {
        "schema": SCHEMA,
        "source_revision": raw["source_revision"],
        "release_digests": releases,
        "total_claim_count": raw["total_claim_count"],
        "production_deployment_authorized": False,
    }
    digest = sha256(_canonical(payload)).hexdigest()
    if not isinstance(raw.get("index_digest"), str) or raw["index_digest"] != digest:
        raise ValueError("release index digest mismatch")

    return PublicationCatalogReleaseIndex(
        source_revision=raw["source_revision"],
        release_digests=tuple(releases),
        total_claim_count=raw["total_claim_count"],
        index_digest=digest,
    )
