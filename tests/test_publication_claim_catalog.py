import pytest

from benchmark.publication_claim_catalog import (
    PublicationClaimCatalogError,
    build_publication_claim_catalog,
)
from benchmark.publication_claim_manifest import build_publication_claim_manifest


def _serialized(claim: str, release_seed: str, artifact_seed: str):
    release = {
        "source_revision": "a" * 40,
        "release_sha256": release_seed * 64,
        "publication_claims_authorized": True,
        "production_deployment_authorized": False,
    }
    built = build_publication_claim_manifest(
        release,
        claims=[claim],
        benchmark_artifacts={f"{artifact_seed}.json": artifact_seed * 64},
    )
    return {
        "schema": built.schema,
        "source_revision": built.source_revision,
        "consensus_release_sha256": built.consensus_release_sha256,
        "benchmark_artifacts": [list(item) for item in built.benchmark_artifacts],
        "claims": list(built.claims),
        "publication_claims_authorized": built.publication_claims_authorized,
        "production_deployment_authorized": built.production_deployment_authorized,
        "manifest_sha256": built.manifest_sha256,
    }


def test_catalog_combines_distinct_verified_manifests():
    catalog = build_publication_claim_catalog([
        _serialized("Latency improved on workload A", "b", "c"),
        _serialized("Peak memory decreased on workload A", "d", "e"),
    ])
    assert catalog.manifest_count == 2
    assert catalog.claim_count == 2
    assert catalog.publication_claims_authorized is True
    assert catalog.production_deployment_authorized is False
    assert len(catalog.catalog_sha256) == 64


def test_duplicate_manifest_is_rejected():
    manifest = _serialized("Latency improved on workload A", "b", "c")
    with pytest.raises(PublicationClaimCatalogError, match="duplicate publication manifests"):
        build_publication_claim_catalog([manifest, manifest])


def test_duplicate_claim_across_distinct_manifests_is_rejected():
    with pytest.raises(PublicationClaimCatalogError, match="duplicate publication claims"):
        build_publication_claim_catalog([
            _serialized("Latency improved on workload A", "b", "c"),
            _serialized("LATENCY IMPROVED ON WORKLOAD A", "d", "e"),
        ])


def test_manifest_tampering_is_rejected_before_cataloging():
    manifest = _serialized("Latency improved on workload A", "b", "c")
    manifest["claims"][0] = "Latency improved everywhere"
    with pytest.raises(PublicationClaimCatalogError, match="invalid publication manifest"):
        build_publication_claim_catalog([manifest])
