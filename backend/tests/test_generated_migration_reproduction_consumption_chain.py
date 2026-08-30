from types import SimpleNamespace

import pytest

from app.generated_migration_reproduction_consumption_chain import verify_generated_migration_reproduction_consumption_chain


def h(ch: str) -> str:
    return ch * 64


def receipt(*, rid: str, consumer: str, predecessor=None, observed_at="2026-08-30T03:00:00Z", attestation=None, purpose="benchmark_claim", authorized=True):
    return SimpleNamespace(
        reproduction_authorized=authorized,
        receipt_sha256=rid,
        attestation_sha256=attestation or h("a"),
        consumer_artifact_sha256=consumer,
        purpose=purpose,
        predecessor_receipt_sha256=predecessor,
        observed_at=observed_at,
    )


def chain():
    first = receipt(rid=h("b"), consumer=h("c"))
    second = receipt(rid=h("d"), consumer=h("e"), predecessor=h("b"), observed_at="2026-08-30T03:01:00Z")
    return [first, second]


def test_chain_is_deterministic_and_authorized():
    assert verify_generated_migration_reproduction_consumption_chain(chain()) == verify_generated_migration_reproduction_consumption_chain(chain())
    assert verify_generated_migration_reproduction_consumption_chain(chain()).reproduction_authorized is True


def test_broken_predecessor_fails_closed():
    values = chain()
    values[1] = receipt(rid=h("d"), consumer=h("e"), predecessor=h("f"), observed_at="2026-08-30T03:01:00Z")
    with pytest.raises(ValueError, match="chain is broken"):
        verify_generated_migration_reproduction_consumption_chain(values)


def test_attestation_and_purpose_cannot_change_mid_chain():
    values = chain()
    values[1] = receipt(rid=h("d"), consumer=h("e"), predecessor=h("b"), observed_at="2026-08-30T03:01:00Z", purpose="research_summary")
    with pytest.raises(ValueError, match="preserve attestation and purpose"):
        verify_generated_migration_reproduction_consumption_chain(values)


def test_duplicate_consumers_and_non_monotonic_time_fail_closed():
    with pytest.raises(ValueError, match="consumer artifacts"):
        verify_generated_migration_reproduction_consumption_chain([receipt(rid=h("b"), consumer=h("c")), receipt(rid=h("d"), consumer=h("c"), predecessor=h("b"), observed_at="2026-08-30T03:01:00Z")])
    with pytest.raises(ValueError, match="monotonic"):
        verify_generated_migration_reproduction_consumption_chain([receipt(rid=h("b"), consumer=h("c"), observed_at="2026-08-30T03:02:00Z"), receipt(rid=h("d"), consumer=h("e"), predecessor=h("b"), observed_at="2026-08-30T03:01:00Z")])


def test_authority_requires_exact_true():
    values = chain()
    values[0] = receipt(rid=h("b"), consumer=h("c"), authorized=1)
    with pytest.raises(ValueError, match="explicitly reproduction-authorized"):
        verify_generated_migration_reproduction_consumption_chain(values)
