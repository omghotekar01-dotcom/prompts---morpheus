from types import SimpleNamespace

import pytest

from app.generated_migration_reproduction_consumption import authorize_generated_migration_reproduction_consumption


def h(ch: str) -> str:
    return ch * 64


def attestation(**overrides):
    values = {
        "reproduction_verified": True,
        "attestation_sha256": h("a"),
        "release_manifest_sha256": h("b"),
        "reproduction_campaign_sha256": h("c"),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def revocation(target=h("a"), revocation_id=h("e"), revoked=True):
    return SimpleNamespace(attestation_sha256=target, revocation_sha256=revocation_id, revoked=revoked)


def build(**overrides):
    values = {
        "attestation": attestation(),
        "revocations": [],
        "purpose": "benchmark_claim",
        "consumer_artifact_sha256": h("d"),
    }
    values.update(overrides)
    return authorize_generated_migration_reproduction_consumption(**values)


def test_unrevoked_attestation_is_authorized_deterministically():
    first = build()
    second = build()
    assert first == second
    assert first.reproduction_authorized is True
    assert first.active_revocation_sha256s == ()


def test_matching_revocation_fails_closed():
    with pytest.raises(ValueError, match="active revocation"):
        build(revocations=[revocation()])


def test_unrelated_revocation_does_not_contaminate_consumption():
    result = build(revocations=[revocation(target=h("f"))])
    assert result.reproduction_authorized is True


@pytest.mark.parametrize("value", [False, 1, "true", None])
def test_attestation_authority_requires_exact_true(value):
    with pytest.raises(ValueError, match="explicitly reproduction-verified"):
        build(attestation=attestation(reproduction_verified=value))


@pytest.mark.parametrize("value", [False, 1, "true", None])
def test_revocation_entries_require_exact_true(value):
    with pytest.raises(ValueError, match="explicitly revoked"):
        build(revocations=[revocation(revoked=value)])


def test_duplicate_revocation_identity_fails_closed():
    with pytest.raises(ValueError, match="unique"):
        build(revocations=[revocation(target=h("f")), revocation(target=h("1"))])


def test_purpose_and_consumer_are_content_addressed():
    baseline = build()
    changed_purpose = build(purpose="research_summary")
    changed_consumer = build(consumer_artifact_sha256=h("f"))
    assert baseline.consumption_sha256 != changed_purpose.consumption_sha256
    assert baseline.consumption_sha256 != changed_consumer.consumption_sha256


def test_aliased_core_identity_is_rejected():
    with pytest.raises(ValueError, match="independent"):
        build(consumer_artifact_sha256=h("a"))
