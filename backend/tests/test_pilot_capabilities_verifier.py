from __future__ import annotations

from copy import deepcopy

from app.pilot_capabilities import pilot_capabilities_payload
from app.pilot_capabilities_verifier import verify_pilot_capabilities


def test_canonical_pilot_capability_ledger_verifies() -> None:
    payload = pilot_capabilities_payload()
    assert verify_pilot_capabilities(payload)
    assert payload["production_deployment_authorized"] is False


def test_verifier_rejects_digest_tampering() -> None:
    payload = pilot_capabilities_payload()
    payload["sha256"] = "0" * 64
    assert not verify_pilot_capabilities(payload)


def test_verifier_rejects_production_authority_promotion_even_if_digest_is_stale() -> None:
    payload = pilot_capabilities_payload()
    payload["production_deployment_authorized"] = True
    assert not verify_pilot_capabilities(payload)


def test_verifier_rejects_scope_widening() -> None:
    payload = pilot_capabilities_payload()
    payload["declared_scope"] = "MULTI_REGION_PRODUCTION"
    assert not verify_pilot_capabilities(payload)


def test_verifier_rejects_blocked_capability_promotion() -> None:
    for capability in (
        "automatic_retry_execution_authority",
        "native_cross_process_hot_swap",
        "high_availability_storage",
        "multi_tenant_identity_and_authorization",
    ):
        payload = deepcopy(pilot_capabilities_payload())
        payload["capabilities"][capability] = "IMPLEMENTED_TESTED"
        assert not verify_pilot_capabilities(payload)


def test_verifier_rejects_malformed_boundaries_and_operator_surfaces() -> None:
    payload = pilot_capabilities_payload()
    payload["truth_boundaries"] = []
    assert not verify_pilot_capabilities(payload)

    payload = pilot_capabilities_payload()
    payload["operator_surfaces"] = {"pilot_preflight": False}
    assert not verify_pilot_capabilities(payload)
