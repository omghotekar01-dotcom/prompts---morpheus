import pytest

from benchmark.publication_catalog_release_bundle import build_release_bundle, verify_release_bundle


def h(ch: str) -> str:
    return ch * 64


def test_release_bundle_round_trip_and_closed_world_schema():
    bundle = build_release_bundle(
        source_revision="a" * 40,
        catalog_digest=h("1"),
        verifier_digest=h("2"),
        manifest_digests=[h("3"), h("4")],
        claim_count=2,
    )
    assert verify_release_bundle(bundle.to_dict()).release_digest == bundle.release_digest

    tampered = bundle.to_dict()
    tampered["runtime_execution_authorized"] = True
    with pytest.raises(ValueError):
        verify_release_bundle(tampered)


def test_duplicate_manifest_and_boolean_claim_count_fail_closed():
    with pytest.raises(ValueError):
        build_release_bundle(
            source_revision="b" * 40,
            catalog_digest=h("1"), verifier_digest=h("2"),
            manifest_digests=[h("3"), h("3")], claim_count=1,
        )
    with pytest.raises(ValueError):
        build_release_bundle(
            source_revision="b" * 40,
            catalog_digest=h("1"), verifier_digest=h("2"),
            manifest_digests=[h("3"), h("4")], claim_count=True,
        )
