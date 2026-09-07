from __future__ import annotations

import pytest

import app.process_transfer_fencing_receipt_restart as restart_module
from app.process_transfer_fencing_receipt import FencedRestartReceiptVerification
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


def test_current_fencing_observation_reverifies_receipt_and_local_restart(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    def load(*args, **kwargs):
        calls.append(("receipt", kwargs["expected_fencing_counter"]))
        return _receipt()

    def read(authority_id: str) -> int:
        calls.append(("external", authority_id))
        return 41

    def verify(*args, **kwargs):
        calls.append(("restart", kwargs["expected_head_sha256"]))
        return _restart()

    monkeypatch.setattr(restart_module, "load_fenced_restart_evidence_receipt", load)
    monkeypatch.setattr(restart_module, "verify_persisted_process_transfer_restart", verify)

    result = restart_module.verify_persisted_fenced_restart_currentness(
        "receipt.json", "head.json", "bundle.bin", read_fencing_counter=read, **_kwargs()
    )

    assert calls == [("receipt", 41), ("external", "fence-a"), ("restart", HEAD)]
    assert result.observed_fencing_counter == 41
    assert result.receipt_replay_verified is True
    assert result.external_counter_observation_verified is True
    assert result.local_restart_evidence_reverified is True
    assert result.exact_receipt_local_binding_verified is True
    assert result.automatic_control_allowed is False
    assert result.activation_allowed is False
    assert result.traffic_switching_allowed is False


def test_invalid_receipt_fails_before_external_resolver_access(monkeypatch) -> None:
    external_called = False

    def fail_load(*args, **kwargs):
        raise ValueError("receipt mismatch")

    def read(authority_id: str) -> int:
        nonlocal external_called
        external_called = True
        return 41

    monkeypatch.setattr(restart_module, "load_fenced_restart_evidence_receipt", fail_load)

    with pytest.raises(ValueError, match="receipt mismatch"):
        restart_module.verify_persisted_fenced_restart_currentness(
            "receipt.json", "head.json", "bundle.bin", read_fencing_counter=read, **_kwargs()
        )
    assert external_called is False


def test_superseded_fencing_counter_fails_before_local_restart_replay(monkeypatch) -> None:
    restart_called = False

    monkeypatch.setattr(restart_module, "load_fenced_restart_evidence_receipt", lambda *a, **k: _receipt())

    def verify(*args, **kwargs):
        nonlocal restart_called
        restart_called = True
        return _restart()

    monkeypatch.setattr(restart_module, "verify_persisted_process_transfer_restart", verify)

    with pytest.raises(ValueError, match="not current"):
        restart_module.verify_persisted_fenced_restart_currentness(
            "receipt.json", "head.json", "bundle.bin", read_fencing_counter=lambda _: 42, **_kwargs()
        )
    assert restart_called is False


@pytest.mark.parametrize("observed", [True, -1, "41", None])
def test_malformed_external_counter_fails_closed(monkeypatch, observed) -> None:
    monkeypatch.setattr(restart_module, "load_fenced_restart_evidence_receipt", lambda *a, **k: _receipt())
    with pytest.raises(ValueError, match="observed_fencing_counter"):
        restart_module.verify_persisted_fenced_restart_currentness(
            "receipt.json", "head.json", "bundle.bin", read_fencing_counter=lambda _: observed, **_kwargs()
        )


def test_external_resolver_failure_is_wrapped(monkeypatch) -> None:
    monkeypatch.setattr(restart_module, "load_fenced_restart_evidence_receipt", lambda *a, **k: _receipt())

    def fail(_authority_id: str) -> int:
        raise RuntimeError("offline")

    with pytest.raises(ValueError, match="current-counter observation failed"):
        restart_module.verify_persisted_fenced_restart_currentness(
            "receipt.json", "head.json", "bundle.bin", read_fencing_counter=fail, **_kwargs()
        )


@pytest.mark.parametrize(
    ("field", "drifted_value"),
    [
        ("authority_id", "receiver-x"),
        ("sequence", 8),
        ("head_sha256", "8" * 64),
        ("bundle_sha256", "9" * 64),
        ("migration_id", "migration-x"),
        ("session_id", "session-x"),
        ("target_candidate_id", "candidate-x"),
    ],
)
def test_each_local_restart_identity_drift_fails_closed(monkeypatch, field, drifted_value) -> None:
    monkeypatch.setattr(restart_module, "load_fenced_restart_evidence_receipt", lambda *a, **k: _receipt())
    monkeypatch.setattr(
        restart_module,
        "verify_persisted_process_transfer_restart",
        lambda *a, **k: _restart(**{field: drifted_value}),
    )

    with pytest.raises(ValueError, match=f"restart {field}"):
        restart_module.verify_persisted_fenced_restart_currentness(
            "receipt.json", "head.json", "bundle.bin", read_fencing_counter=lambda _: 41, **_kwargs()
        )


def test_non_callable_resolver_is_rejected_before_receipt_access(monkeypatch) -> None:
    receipt_called = False

    def load(*args, **kwargs):
        nonlocal receipt_called
        receipt_called = True
        return _receipt()

    monkeypatch.setattr(restart_module, "load_fenced_restart_evidence_receipt", load)

    with pytest.raises(ValueError, match="read_fencing_counter must be callable"):
        restart_module.verify_persisted_fenced_restart_currentness(
            "receipt.json", "head.json", "bundle.bin", read_fencing_counter=41, **_kwargs()
        )
    assert receipt_called is False
