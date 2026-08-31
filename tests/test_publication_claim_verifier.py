import pytest

from benchmark.publication_claim_manifest import build_publication_claim_manifest
from benchmark.publication_claim_verifier import (
    PublicationClaimVerificationError,
    verify_publication_claim_manifest,
)


def _release():
    return {
        "source_revision": "a" * 40,
        "release_sha256": "b" * 64,
        "publication_claims_authorized": True,
        "production_deployment_authorized": False,
    }


def _serialized():
    built = build_publication_claim_manifest(
        _release(),
        claims=["Latency improved on workload A", "Peak memory decreased"],
        benchmark_artifacts={"results.json": "c" * 64, "profile.json": "d" * 64},
    )
    return {
        "source_revision": built.source_revision,
        "consensus_release_sha256": built.consensus_release_sha256,
        "benchmark_artifacts": [list(x) for x in built.benchmark_artifacts],
        "claims": list(built.claims),
        "publication_claims_authorized": built.publication_claims_authorized,
        "production_deployment_authorized": built.production_deployment_authorized,
        "manifest_sha256": built.manifest_sha256,
    }


def test_independent_verifier_accepts_builder_output():
    manifest = _serialized()
    assert verify_publication_claim_manifest(manifest) == manifest["manifest_sha256"]


def test_claim_tampering_fails_closed():
    manifest = _serialized()
    manifest["claims"][0] = "Latency improved on every possible workload"
    with pytest.raises(PublicationClaimVerificationError, match="digest mismatch"):
        verify_publication_claim_manifest(manifest)


def test_artifact_substitution_fails_closed():
    manifest = _serialized()
    manifest["benchmark_artifacts"][0][1] = "e" * 64
    with pytest.raises(PublicationClaimVerificationError, match="digest mismatch"):
        verify_publication_claim_manifest(manifest)


def test_production_authority_escalation_is_rejected():
    manifest = _serialized()
    manifest["production_deployment_authorized"] = True
    with pytest.raises(PublicationClaimVerificationError, match="must not authorize"):
        verify_publication_claim_manifest(manifest)


def test_aliasing_is_rejected_before_digest_check():
    manifest = _serialized()
    manifest["benchmark_artifacts"][1][1] = manifest["benchmark_artifacts"][0][1]
    with pytest.raises(PublicationClaimVerificationError, match="unique and non-aliased"):
        verify_publication_claim_manifest(manifest)


def test_shadow_authority_field_is_rejected_even_with_valid_digest():
    manifest = _serialized()
    manifest["runtime_execution_authorized"] = True
    with pytest.raises(PublicationClaimVerificationError, match="undeclared fields"):
        verify_publication_claim_manifest(manifest)


def test_missing_required_field_is_rejected_explicitly():
    manifest = _serialized()
    del manifest["claims"]
    with pytest.raises(PublicationClaimVerificationError, match="missing required fields"):
        verify_publication_claim_manifest(manifest)
