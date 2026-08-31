import pytest

from publication_claim_manifest import build_publication_claim_manifest


def _h(ch: str) -> str:
    return ch * 64


def _release():
    return {
        "source_revision": "a" * 40,
        "release_sha256": _h("1"),
        "publication_claims_authorized": True,
        "production_deployment_authorized": False,
    }


def test_manifest_is_deterministic_across_claim_and_artifact_order():
    first = build_publication_claim_manifest(
        _release(),
        claims=["MORPHEUS beats baseline A on workload W.", "Median latency improves under protocol P."],
        benchmark_artifacts={"summary.json": _h("2"), "raw.csv": _h("3")},
    )
    second = build_publication_claim_manifest(
        _release(),
        claims=["Median latency improves under protocol P.", "MORPHEUS beats baseline A on workload W."],
        benchmark_artifacts={"raw.csv": _h("3"), "summary.json": _h("2")},
    )
    assert first == second
    assert first.publication_claims_authorized
    assert not first.production_deployment_authorized


def test_unreleased_publication_claims_fail_closed():
    release = _release()
    release["publication_claims_authorized"] = False
    with pytest.raises(ValueError, match="does not authorize"):
        build_publication_claim_manifest(release, claims=["claim"], benchmark_artifacts={"a": _h("2")})


def test_production_authority_is_rejected():
    release = _release()
    release["production_deployment_authorized"] = True
    with pytest.raises(ValueError, match="production authority"):
        build_publication_claim_manifest(release, claims=["claim"], benchmark_artifacts={"a": _h("2")})


def test_evidence_aliasing_is_rejected():
    with pytest.raises(ValueError, match="must not alias"):
        build_publication_claim_manifest(_release(), claims=["claim"], benchmark_artifacts={"a": _h("1")})


def test_duplicate_claims_and_malformed_hashes_are_rejected():
    with pytest.raises(ValueError, match="unique"):
        build_publication_claim_manifest(_release(), claims=["same", "same"], benchmark_artifacts={"a": _h("2")})
    with pytest.raises(ValueError, match="SHA-256"):
        build_publication_claim_manifest(_release(), claims=["claim"], benchmark_artifacts={"a": "not-a-hash"})
