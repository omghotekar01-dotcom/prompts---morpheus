from __future__ import annotations

import pytest

import app.process_transfer_protected_resource_fencing as protected_module
from app.process_transfer_fencing_receipt import FencedRestartReceiptVerification
from app.process_transfer_protected_resource_fencing import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    ProtectedResourceFencingDecision,
)
from app.process_transfer_restart import ProcessTransferRestartVerification


HEAD = "1" * 64
BUNDLE = "2" * 64
RECEIPT = "3" * 64


def _receipt(**overrides) -> FencedRestartReceiptVerification:
    values = dict(
        receipt_sha256=RECEIPT,
        receipt_size_bytes=123,
        key_id="key-1",
        authority_id="receiver-a",
        sequence=7,
        head_sha256=HEAD,
        bundle_sha256=BUNDLE,
        migration_id="migration-7",
        session_id="session-7",
        target_candidate_id="candidate-b",
        fencing_authority_id="fence-a",
        previous_fencing_counter=40,
        fencing_counter=41,
    )
    values.update(overrides)
    return FencedRestartReceiptVerification(**values)


def _restart(**overrides) -> ProcessTransferRestartVerification:
    values = dict(
        authority_id="receiver-a",
        sequence=7,
        previous_head_sha256="0" * 64,
        bundle_sha256=BUNDLE,
        migration_id="migration-7",
        session_id="session-7",
        target_candidate_id="candidate-b",
        head_sha256=HEAD,
    )
    values.update(overrides)
    return ProcessTransferRestartVerification(**values)


def _kwargs() -> dict[str, object]:
    return {
        "protected_resource_id": "resource-a",
        "expected_key_id": "key-1",
        "expected_authority_id": "receiver-a",
        "expected_sequence": 7,
        "expected_head_sha256": HEAD,
        "expected_bundle_sha256": BUNDLE,
        "expected_migration_id": "migration-7",
        "expected_session_id": "session-7",
        "expected_target_candidate_id": "candidate-b",
        "expected_fencing_authority_id": "fence-a",
        "expected_previous_fencing_counter": 40,
        "expected_fencing_counter": 41,
        "expected_schema_identity": "schema-v1",
        "expected_codec_identity": "codec-v1",
        "expected_target_artifact_sha256": "4" * 64,
        "expected_verification_manifest_sha256": "5" * 64,
    }


def _accepted(**overrides) -> ProtectedResourceFencingDecision:
    values = dict(
        resource_id="resource-a",
        fencing_authority_id="fence-a",
        fencing_counter=41,
        accepted=True,
    )
    values.update(overrides)
    return ProtectedResourceFencingDecision(**values)


def test_protected_resource_token_validation_occurs_after_exact_local_replay(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    def load(*args, **kwargs):
        calls.append(("receipt", kwargs["expected_fencing_counter"]))
        return _receipt()

    def verify(*args, **kwargs):
        calls.append(("restart", kwargs["expected_head_sha256"]))
        return _restart()

    def validate(resource_id: str, authority_id: str, counter: int) -> ProtectedResourceFencingDecision:
        calls.append(("protected-resource", (resource_id, authority_id, counter)))
        return _accepted()

    monkeypatch.setattr(protected_module, "load_fenced_restart_evidence_receipt", load)
    monkeypatch.setattr(protected_module, "verify_persisted_process_transfer_restart", verify)

    result = protected_module.verify_persisted_fenced_restart_protected_resource_token(
        "receipt.json", "head.json", "bundle.bin", validate_fencing_token=validate, **_kwargs()
    )

    assert calls == [
        ("receipt", 41),
        ("restart", HEAD),
        ("protected-resource", ("resource-a", "fence-a", 41)),
    ]
    assert result.protected_resource_id == "resource-a"
    assert result.fencing_counter == 41
    assert result.receipt_replay_verified is True
    assert result.local_restart_evidence_reverified is True
    assert result.exact_receipt_local_binding_verified is True
    assert result.protected_resource_identity_verified is True
    assert result.protected_resource_fencing_token_accepted is True
    assert result.automatic_control_allowed is False
    assert result.activation_allowed is False
    assert result.traffic_switching_allowed is False
    assert result.evidence_state == EVIDENCE_STATE


def test_invalid_receipt_fails_before_local_or_protected_resource_access(monkeypatch) -> None:
    restart_called = False
    consumer_called = False

    def fail_load(*args, **kwargs):
        raise ValueError("receipt mismatch")

    def verify(*args, **kwargs):
        nonlocal restart_called
        restart_called = True
        return _restart()

    def validate(*args) -> ProtectedResourceFencingDecision:
        nonlocal consumer_called
        consumer_called = True
        return _accepted()

    monkeypatch.setattr(protected_module, "load_fenced_restart_evidence_receipt", fail_load)
    monkeypatch.setattr(protected_module, "verify_persisted_process_transfer_restart", verify)

    with pytest.raises(ValueError, match="receipt mismatch"):
        protected_module.verify_persisted_fenced_restart_protected_resource_token(
            "receipt.json", "head.json", "bundle.bin", validate_fencing_token=validate, **_kwargs()
        )
    assert restart_called is False
    assert consumer_called is False


def test_local_identity_drift_fails_before_protected_resource_access(monkeypatch) -> None:
    consumer_called = False
    monkeypatch.setattr(protected_module, "load_fenced_restart_evidence_receipt", lambda *a, **k: _receipt())
    monkeypatch.setattr(
        protected_module,
        "verify_persisted_process_transfer_restart",
        lambda *a, **k: _restart(head_sha256="8" * 64),
    )

    def validate(*args) -> ProtectedResourceFencingDecision:
        nonlocal consumer_called
        consumer_called = True
        return _accepted()

    with pytest.raises(ValueError, match="restart head_sha256"):
        protected_module.verify_persisted_fenced_restart_protected_resource_token(
            "receipt.json", "head.json", "bundle.bin", validate_fencing_token=validate, **_kwargs()
        )
    assert consumer_called is False


def test_protected_resource_rejection_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(protected_module, "load_fenced_restart_evidence_receipt", lambda *a, **k: _receipt())
    monkeypatch.setattr(protected_module, "verify_persisted_process_transfer_restart", lambda *a, **k: _restart())

    with pytest.raises(ValueError, match="rejected"):
        protected_module.verify_persisted_fenced_restart_protected_resource_token(
            "receipt.json",
            "head.json",
            "bundle.bin",
            validate_fencing_token=lambda *a: _accepted(accepted=False),
            **_kwargs(),
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"resource_id": "resource-x"}, "resource_id"),
        ({"fencing_authority_id": "fence-x"}, "fencing_authority_id"),
        ({"fencing_counter": 42}, "fencing_counter does not match"),
        ({"fencing_counter": True}, "fencing_counter must be"),
        ({"fencing_counter": -1}, "fencing_counter must be"),
        ({"accepted": 1}, "accepted must be boolean"),
    ],
)
def test_consumer_identity_or_shape_drift_fails_closed(monkeypatch, overrides, message) -> None:
    monkeypatch.setattr(protected_module, "load_fenced_restart_evidence_receipt", lambda *a, **k: _receipt())
    monkeypatch.setattr(protected_module, "verify_persisted_process_transfer_restart", lambda *a, **k: _restart())

    with pytest.raises(ValueError, match=message):
        protected_module.verify_persisted_fenced_restart_protected_resource_token(
            "receipt.json",
            "head.json",
            "bundle.bin",
            validate_fencing_token=lambda *a: _accepted(**overrides),
            **_kwargs(),
        )


def test_malformed_consumer_return_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(protected_module, "load_fenced_restart_evidence_receipt", lambda *a, **k: _receipt())
    monkeypatch.setattr(protected_module, "verify_persisted_process_transfer_restart", lambda *a, **k: _restart())

    with pytest.raises(ValueError, match="must return ProtectedResourceFencingDecision"):
        protected_module.verify_persisted_fenced_restart_protected_resource_token(
            "receipt.json", "head.json", "bundle.bin", validate_fencing_token=lambda *a: True, **_kwargs()
        )


def test_consumer_failure_is_wrapped(monkeypatch) -> None:
    monkeypatch.setattr(protected_module, "load_fenced_restart_evidence_receipt", lambda *a, **k: _receipt())
    monkeypatch.setattr(protected_module, "verify_persisted_process_transfer_restart", lambda *a, **k: _restart())

    def fail(*args) -> ProtectedResourceFencingDecision:
        raise RuntimeError("offline")

    with pytest.raises(ValueError, match="fencing-token validation failed"):
        protected_module.verify_persisted_fenced_restart_protected_resource_token(
            "receipt.json", "head.json", "bundle.bin", validate_fencing_token=fail, **_kwargs()
        )


@pytest.mark.parametrize("resource_id", ["", "   ", None, 7])
def test_invalid_protected_resource_identity_is_rejected_before_receipt_access(monkeypatch, resource_id) -> None:
    receipt_called = False

    def load(*args, **kwargs):
        nonlocal receipt_called
        receipt_called = True
        return _receipt()

    monkeypatch.setattr(protected_module, "load_fenced_restart_evidence_receipt", load)
    kwargs = _kwargs()
    kwargs["protected_resource_id"] = resource_id

    with pytest.raises(ValueError, match="protected_resource_id must be a non-empty string"):
        protected_module.verify_persisted_fenced_restart_protected_resource_token(
            "receipt.json", "head.json", "bundle.bin", validate_fencing_token=lambda *a: _accepted(), **kwargs
        )
    assert receipt_called is False


def test_non_callable_consumer_is_rejected_before_receipt_access(monkeypatch) -> None:
    receipt_called = False

    def load(*args, **kwargs):
        nonlocal receipt_called
        receipt_called = True
        return _receipt()

    monkeypatch.setattr(protected_module, "load_fenced_restart_evidence_receipt", load)

    with pytest.raises(ValueError, match="validate_fencing_token must be callable"):
        protected_module.verify_persisted_fenced_restart_protected_resource_token(
            "receipt.json", "head.json", "bundle.bin", validate_fencing_token=41, **_kwargs()
        )
    assert receipt_called is False


def test_truth_boundary_denies_cutover_and_scientific_claims() -> None:
    lowered = TRUTH_BOUNDARY.lower()
    assert "does not prove" in lowered
    assert "not an atomic cutover" in lowered
    assert "traffic switching remain forbidden" in lowered
    assert "no benchmark" in lowered
    assert "production-readiness claim" in lowered
