from types import SimpleNamespace

import pytest

from app.generated_migration_reproduction_consumption_receipt import record_generated_migration_reproduction_consumption


def h(ch: str) -> str:
    return ch * 64


def consumption(**overrides):
    values = {
        "reproduction_authorized": True,
        "consumption_sha256": h("a"),
        "attestation_sha256": h("b"),
        "consumer_artifact_sha256": h("c"),
        "purpose": "benchmark_claim",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def build(**overrides):
    values = {
        "consumption": consumption(),
        "observed_at": "2026-08-30T02:00:00+00:00",
        "observer_artifact_sha256": h("d"),
    }
    values.update(overrides)
    return record_generated_migration_reproduction_consumption(**values)


def test_receipt_is_deterministic_and_authorized():
    assert build() == build()
    assert build().reproduction_authorized is True


@pytest.mark.parametrize("value", [False, 1, "true", None])
def test_consumption_authority_requires_exact_true(value):
    with pytest.raises(ValueError, match="explicitly reproduction-authorized"):
        build(consumption=consumption(reproduction_authorized=value))


def test_timestamp_is_normalized_to_utc():
    receipt = build(observed_at="2026-08-30T07:30:00+05:30")
    assert receipt.observed_at == "2026-08-30T02:00:00Z"


def test_naive_timestamp_fails_closed():
    with pytest.raises(ValueError, match="timezone-aware"):
        build(observed_at="2026-08-30T02:00:00")


def test_predecessor_is_content_addressed():
    assert build().receipt_sha256 != build(predecessor_receipt_sha256=h("e")).receipt_sha256


def test_identity_aliasing_is_rejected():
    with pytest.raises(ValueError, match="independent"):
        build(observer_artifact_sha256=h("a"))


def test_observer_and_time_change_receipt_identity():
    baseline = build()
    assert baseline.receipt_sha256 != build(observer_artifact_sha256=h("e")).receipt_sha256
    assert baseline.receipt_sha256 != build(observed_at="2026-08-30T02:00:01Z").receipt_sha256
