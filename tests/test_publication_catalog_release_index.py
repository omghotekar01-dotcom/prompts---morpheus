import pytest

from benchmark.publication_catalog_release_bundle import build_release_bundle
from benchmark.publication_catalog_release_index import (
    build_release_index,
    verify_release_index,
    verify_release_index_against_bundles,
)


def h(ch: str) -> str:
    return ch * 64


def bundle(revision: str, suffix: str, claims: int = 2):
    return build_release_bundle(
        source_revision=revision,
        catalog_digest=h(suffix),
        verifier_digest=h("f"),
        manifest_digests=[h("1"), h("2")],
        claim_count=claims,
    ).to_dict()


def test_release_index_round_trip_and_canonical_order():
    revision = "a" * 40
    index = build_release_index([bundle(revision, "4", 3), bundle(revision, "3", 2)])
    verified = verify_release_index(index.to_dict())

    assert verified.index_digest == index.index_digest
    assert verified.total_claim_count == 5
    assert list(verified.release_digests) == sorted(verified.release_digests)
    assert verified.production_deployment_authorized is False


def test_mixed_revision_and_duplicate_release_fail_closed():
    with pytest.raises(ValueError, match="same source revision"):
        build_release_index([bundle("a" * 40, "3"), bundle("b" * 40, "4")])

    repeated = bundle("a" * 40, "3")
    with pytest.raises(ValueError, match="unique"):
        build_release_index([repeated, repeated])


def test_tampering_shadow_authority_and_noncanonical_order_fail_closed():
    revision = "c" * 40
    index = build_release_index([bundle(revision, "3"), bundle(revision, "4")])

    tampered = index.to_dict()
    tampered["total_claim_count"] += 1
    with pytest.raises(ValueError, match="digest mismatch"):
        verify_release_index(tampered)

    shadow = index.to_dict()
    shadow["runtime_execution_authorized"] = True
    with pytest.raises(ValueError, match="closed v1 schema"):
        verify_release_index(shadow)

    reordered = index.to_dict()
    reordered["release_digests"] = list(reversed(reordered["release_digests"]))
    with pytest.raises(ValueError, match="canonical-order"):
        verify_release_index(reordered)


def test_boolean_claim_total_fails_closed():
    revision = "d" * 40
    raw = build_release_index([bundle(revision, "3"), bundle(revision, "4")]).to_dict()
    raw["total_claim_count"] = True
    with pytest.raises(ValueError, match="integer"):
        verify_release_index(raw)


def test_index_can_be_verified_against_exact_release_evidence():
    revision = "e" * 40
    bundles = [bundle(revision, "3", 2), bundle(revision, "4", 5)]
    raw = build_release_index(bundles).to_dict()

    verified = verify_release_index_against_bundles(raw, reversed(bundles))

    assert verified.total_claim_count == 7
    assert verified.production_deployment_authorized is False


def test_missing_or_unindexed_release_evidence_fails_closed():
    revision = "a" * 40
    indexed = [bundle(revision, "3"), bundle(revision, "4")]
    raw = build_release_index(indexed).to_dict()

    with pytest.raises(ValueError, match="at least two"):
        verify_release_index_against_bundles(raw, indexed[:1])

    replacement = [indexed[0], bundle(revision, "5")]
    with pytest.raises(ValueError, match="exactly match"):
        verify_release_index_against_bundles(raw, replacement)


def test_replayed_release_evidence_fails_closed():
    revision = "b" * 40
    indexed = [bundle(revision, "3"), bundle(revision, "4")]
    raw = build_release_index(indexed).to_dict()

    with pytest.raises(ValueError, match="replayed"):
        verify_release_index_against_bundles(raw, [indexed[0], indexed[0]])
