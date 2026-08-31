from __future__ import annotations

import pytest

from app import pilot_startup_evidence as startup_evidence


SOURCE_REVISION = "822532f1b92b7a4e8ec87f519c1b15b0f23378ec"


def _capabilities() -> dict[str, object]:
    return {
        "sha256": "a" * 64,
        "production_deployment_authorized": False,
    }


def _readiness(*, ready: bool = True) -> dict[str, object]:
    return {
        "readiness_sha256": "b" * 64,
        "ready": ready,
    }


def _launch_plan() -> dict[str, object]:
    return {
        "sha256": "c" * 64,
        "production_deployment_authorized": False,
    }


def _trust_existing_receipts(monkeypatch) -> None:
    monkeypatch.setattr(startup_evidence, "verify_pilot_capabilities", lambda payload: True)
    monkeypatch.setattr(startup_evidence, "verify_pilot_readiness", lambda payload: True)


def test_startup_evidence_is_deterministic_and_verifiable(monkeypatch) -> None:
    _trust_existing_receipts(monkeypatch)
    kwargs = {
        "capabilities": _capabilities(),
        "readiness": _readiness(),
        "launch_plan": _launch_plan(),
        "source_revision": SOURCE_REVISION,
        "api_contract_sha256": "d" * 64,
        "feature_policy_sha256": "e" * 64,
    }
    first = startup_evidence.build_pilot_startup_evidence(**kwargs)
    second = startup_evidence.build_pilot_startup_evidence(**kwargs)

    assert first == second
    assert startup_evidence.verify_pilot_startup_evidence(first)
    assert first["production_deployment_authorized"] is False
    assert first["source_revision"] == SOURCE_REVISION
    assert first["fingerprints"] == {
        "api_contract_sha256": "d" * 64,
        "feature_policy_sha256": "e" * 64,
    }


def test_builder_fails_closed_when_upstream_receipts_are_not_verified(monkeypatch) -> None:
    monkeypatch.setattr(startup_evidence, "verify_pilot_capabilities", lambda payload: False)
    monkeypatch.setattr(startup_evidence, "verify_pilot_readiness", lambda payload: True)
    with pytest.raises(ValueError, match="capability ledger failed verification"):
        startup_evidence.build_pilot_startup_evidence(
            capabilities=_capabilities(),
            readiness=_readiness(),
            launch_plan=_launch_plan(),
            source_revision=SOURCE_REVISION,
        )

    monkeypatch.setattr(startup_evidence, "verify_pilot_capabilities", lambda payload: True)
    monkeypatch.setattr(startup_evidence, "verify_pilot_readiness", lambda payload: False)
    with pytest.raises(ValueError, match="readiness receipt failed verification"):
        startup_evidence.build_pilot_startup_evidence(
            capabilities=_capabilities(),
            readiness=_readiness(),
            launch_plan=_launch_plan(),
            source_revision=SOURCE_REVISION,
        )


def test_builder_rejects_valid_but_blocked_readiness_and_widened_authority(monkeypatch) -> None:
    _trust_existing_receipts(monkeypatch)
    with pytest.raises(ValueError, match="valid but not ready"):
        startup_evidence.build_pilot_startup_evidence(
            capabilities=_capabilities(),
            readiness=_readiness(ready=False),
            launch_plan=_launch_plan(),
            source_revision=SOURCE_REVISION,
        )

    capabilities = _capabilities()
    capabilities["production_deployment_authorized"] = True
    with pytest.raises(ValueError, match="deny production deployment"):
        startup_evidence.build_pilot_startup_evidence(
            capabilities=capabilities,
            readiness=_readiness(),
            launch_plan=_launch_plan(),
            source_revision=SOURCE_REVISION,
        )

    launch_plan = _launch_plan()
    launch_plan["production_deployment_authorized"] = True
    with pytest.raises(ValueError, match="launch plan must deny production deployment"):
        startup_evidence.build_pilot_startup_evidence(
            capabilities=_capabilities(),
            readiness=_readiness(),
            launch_plan=launch_plan,
            source_revision=SOURCE_REVISION,
        )


def test_startup_evidence_verifier_rejects_tampering(monkeypatch) -> None:
    _trust_existing_receipts(monkeypatch)
    receipt = startup_evidence.build_pilot_startup_evidence(
        capabilities=_capabilities(),
        readiness=_readiness(),
        launch_plan=_launch_plan(),
        source_revision=SOURCE_REVISION,
    )

    for key, replacement in (
        ("source_revision", "deadbee"),
        ("capability_sha256", "f" * 64),
        ("readiness_sha256", "f" * 64),
        ("launch_plan_sha256", "f" * 64),
        ("production_deployment_authorized", True),
    ):
        tampered = dict(receipt)
        tampered[key] = replacement
        assert not startup_evidence.verify_pilot_startup_evidence(tampered)

    extra = dict(receipt)
    extra["production_token"] = "forged"
    assert not startup_evidence.verify_pilot_startup_evidence(extra)


def test_builder_rejects_noncanonical_source_revision_and_fingerprints(monkeypatch) -> None:
    _trust_existing_receipts(monkeypatch)
    for revision in ("ABCDEF1", "abc123", "g" * 40, "a" * 41):
        with pytest.raises(ValueError, match="source_revision"):
            startup_evidence.build_pilot_startup_evidence(
                capabilities=_capabilities(),
                readiness=_readiness(),
                launch_plan=_launch_plan(),
                source_revision=revision,
            )

    with pytest.raises(ValueError, match="api_contract_sha256"):
        startup_evidence.build_pilot_startup_evidence(
            capabilities=_capabilities(),
            readiness=_readiness(),
            launch_plan=_launch_plan(),
            source_revision=SOURCE_REVISION,
            api_contract_sha256="not-a-digest",
        )
