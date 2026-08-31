import pytest

from benchmark.publication_claim_catalog import build_publication_claim_catalog
from benchmark.publication_claim_catalog_verifier import verify_publication_claim_catalog
from benchmark.publication_claim_manifest import build_publication_claim_manifest


def _manifest(claim: str, release_seed: str, artifact_seed: str):
    built = build_publication_claim_manifest(
        {"source_revision": "a" * 40, "release_sha256": release_seed * 64,
         "publication_claims_authorized": True, "production_deployment_authorized": False},
        claims=[claim], benchmark_artifacts={f"{artifact_seed}.json": artifact_seed * 64})
    return {"schema": built.schema, "source_revision": built.source_revision,
            "consensus_release_sha256": built.consensus_release_sha256,
            "benchmark_artifacts": [list(x) for x in built.benchmark_artifacts],
            "claims": list(built.claims), "publication_claims_authorized": True,
            "production_deployment_authorized": False, "manifest_sha256": built.manifest_sha256}


def _catalog():
    built = build_publication_claim_catalog([
        _manifest("Latency improved on workload A", "b", "c"),
        _manifest("Peak memory decreased on workload A", "d", "e")])
    return {"schema": "morpheus.publication_claim_catalog.v1",
            "source_revision": built.source_revision, "manifest_count": built.manifest_count,
            "claim_count": built.claim_count, "manifest_sha256": list(built.manifest_sha256),
            "claims": list(built.claims), "catalog_sha256": built.catalog_sha256,
            "publication_claims_authorized": True, "production_deployment_authorized": False}


def test_independent_verifier_accepts_valid_serialized_catalog():
    catalog = _catalog()
    assert verify_publication_claim_catalog(catalog) == catalog["catalog_sha256"]


def test_claim_tampering_is_rejected():
    catalog = _catalog(); catalog["claims"][0] = "Latency improved everywhere"
    with pytest.raises(ValueError, match="digest mismatch"):
        verify_publication_claim_catalog(catalog)


def test_shadow_authority_field_is_rejected():
    catalog = _catalog(); catalog["runtime_execution_authorized"] = True
    with pytest.raises(ValueError, match="closed schema"):
        verify_publication_claim_catalog(catalog)


def test_reordered_evidence_is_rejected_even_before_digest_check():
    catalog = _catalog(); catalog["manifest_sha256"].reverse()
    with pytest.raises(ValueError, match="canonically ordered"):
        verify_publication_claim_catalog(catalog)


def test_count_alias_and_production_authority_are_rejected():
    catalog = _catalog(); catalog["manifest_count"] = True
    with pytest.raises(ValueError, match="manifest_count"):
        verify_publication_claim_catalog(catalog)
    catalog = _catalog(); catalog["production_deployment_authorized"] = True
    with pytest.raises(ValueError, match="forbidden"):
        verify_publication_claim_catalog(catalog)
