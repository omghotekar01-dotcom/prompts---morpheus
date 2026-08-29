from types import SimpleNamespace

import pytest

from app.generated_migration_reproduction_attestation import attest_generated_migration_reproduction


def h(ch: str) -> str:
    return ch * 64


def campaign(**overrides):
    values = {
        "reproduction_campaign_verified": True,
        "release_manifest_sha256": h("a"),
        "campaign_sha256": h("b"),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def build(**overrides):
    values = {
        "campaign": campaign(),
        "publication_bundle_sha256": h("c"),
        "archive_artifact_sha256": h("d"),
        "attestation_policy_sha256": h("e"),
    }
    values.update(overrides)
    return attest_generated_migration_reproduction(**values)


def test_attestation_is_deterministic_and_verified():
    first = build()
    second = build()
    assert first == second
    assert first.reproduction_verified is True
    assert first.schema == "morpheus.generated_migration_reproduction_attestation.v1"
    assert len(first.attestation_sha256) == 64


def test_unverified_campaign_fails_closed():
    with pytest.raises(ValueError, match="explicitly reproduction-verified"):
        build(campaign=campaign(reproduction_campaign_verified=False))


@pytest.mark.parametrize("value", [1, "true", None])
def test_truthy_or_non_boolean_verification_cannot_authorize(value):
    with pytest.raises(ValueError, match="explicitly reproduction-verified"):
        build(campaign=campaign(reproduction_campaign_verified=value))


def test_placeholder_or_malformed_identity_is_rejected():
    with pytest.raises(ValueError, match="archive_artifact_sha256"):
        build(archive_artifact_sha256="0" * 64)
    with pytest.raises(ValueError, match="attestation_policy_sha256"):
        build(attestation_policy_sha256="not-a-hash")


def test_identity_aliasing_is_rejected():
    with pytest.raises(ValueError, match="identities must be independent"):
        build(archive_artifact_sha256=h("c"))


def test_policy_change_changes_attestation_identity():
    baseline = build()
    changed = build(attestation_policy_sha256=h("f"))
    assert baseline.attestation_sha256 != changed.attestation_sha256
