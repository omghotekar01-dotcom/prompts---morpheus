from types import SimpleNamespace

import pytest

from app.generated_migration_reproduction_revocation import revoke_generated_migration_reproduction


def h(ch: str) -> str:
    return ch * 64


def attestation(**overrides):
    values = {"reproduction_verified": True, "attestation_sha256": h("a")}
    values.update(overrides)
    return SimpleNamespace(**values)


def build(**overrides):
    values = {
        "attestation": attestation(),
        "reason": "reproduction_evidence_invalidated",
        "evidence_sha256s": [h("b"), h("c")],
    }
    values.update(overrides)
    return revoke_generated_migration_reproduction(**values)


def test_revocation_is_deterministic_and_order_independent():
    first = build()
    second = build(evidence_sha256s=[h("c"), h("b")])
    assert first == second
    assert first.revoked is True
    assert first.schema == "morpheus.generated_migration_reproduction_revocation.v1"


def test_unverified_attestation_fails_closed():
    with pytest.raises(ValueError, match="explicitly reproduction-verified"):
        build(attestation=attestation(reproduction_verified=False))


@pytest.mark.parametrize("value", [1, "true", None])
def test_non_boolean_verification_cannot_authorize_revocation(value):
    with pytest.raises(ValueError, match="explicitly reproduction-verified"):
        build(attestation=attestation(reproduction_verified=value))


def test_duplicate_or_aliased_evidence_is_rejected():
    with pytest.raises(ValueError, match="unique"):
        build(evidence_sha256s=[h("b"), h("b")])
    with pytest.raises(ValueError, match="independent"):
        build(evidence_sha256s=[h("a")])


def test_predecessor_is_bound_and_independent():
    baseline = build()
    chained = build(predecessor_revocation_sha256=h("d"))
    assert baseline.revocation_sha256 != chained.revocation_sha256
    with pytest.raises(ValueError, match="independent"):
        build(predecessor_revocation_sha256=h("b"))


def test_unknown_reason_fails_closed():
    with pytest.raises(ValueError, match="unsupported"):
        build(reason="because")
