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


def test_bracketed_currentness_reads_same_generation_before_and_after_local_replay(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []
    observations = iter([41, 41])

    def load(*args, **kwargs):
        calls.append(("receipt", kwargs["expected_fencing_counter"]))
        return _receipt()

    def read(authority_id: str) -> int:
        calls.append(("external", authority_id))
        return next(observations)

    def verify(*args, **kwargs):
        calls.append(("restart", kwargs["expected_head_sha256"]))
        return _restart()

    monkeypatch.setattr(restart_module, "load_fenced_restart_evidence_receipt", load)
    monkeypatch.setattr(restart_module, "verify_persisted_process_transfer_restart", verify)

    result = restart_module.verify_persisted_fenced_restart_bracketed_currentness(
        "receipt.json", "head.json", "bundle.bin", read_fencing_counter=read, **_kwargs()
    )

    assert calls == [
        ("receipt", 41),
        ("external", "fence-a"),
        ("restart", HEAD),
        ("external", "fence-a"),
    ]
    assert result.observed_fencing_counter_before == 41
    assert result.observed_fencing_counter_after == 41
    assert result.bracketed_counter_equality_verified is True
    assert result.automatic_control_allowed is False
    assert result.activation_allowed is False
    assert result.traffic_switching_allowed is False
    assert "not an atomic snapshot" in result.truth_boundary


def test_pre_replay_supersession_fails_before_local_replay_and_second_read(monkeypatch) -> None:
    restart_called = False
    read_count = 0
    monkeypatch.setattr(restart_module, "load_fenced_restart_evidence_receipt", lambda *a, **k: _receipt())

    def read(_authority_id: str) -> int:
        nonlocal read_count
        read_count += 1
        return 42

    def verify(*args, **kwargs):
        nonlocal restart_called
        restart_called = True
        return _restart()

    monkeypatch.setattr(restart_module, "verify_persisted_process_transfer_restart", verify)

    with pytest.raises(ValueError, match="pre-replay"):
        restart_module.verify_persisted_fenced_restart_bracketed_currentness(
            "receipt.json", "head.json", "bundle.bin", read_fencing_counter=read, **_kwargs()
        )
    assert restart_called is False
    assert read_count == 1


def test_post_replay_supersession_is_detected_after_exact_local_replay(monkeypatch) -> None:
    observations = iter([41, 42])
    restart_called = False
    monkeypatch.setattr(restart_module, "load_fenced_restart_evidence_receipt", lambda *a, **k: _receipt())

    def verify(*args, **kwargs):
        nonlocal restart_called
        restart_called = True
        return _restart()

    monkeypatch.setattr(restart_module, "verify_persisted_process_transfer_restart", verify)

    with pytest.raises(ValueError, match="superseded"):
        restart_module.verify_persisted_fenced_restart_bracketed_currentness(
            "receipt.json",
            "head.json",
            "bundle.bin",
            read_fencing_counter=lambda _: next(observations),
            **_kwargs(),
        )
    assert restart_called is True


@pytest.mark.parametrize("bad", [True, -1, "41", None])
def test_malformed_post_replay_counter_fails_closed(monkeypatch, bad) -> None:
    observations = iter([41, bad])
    monkeypatch.setattr(restart_module, "load_fenced_restart_evidence_receipt", lambda *a, **k: _receipt())
    monkeypatch.setattr(restart_module, "verify_persisted_process_transfer_restart", lambda *a, **k: _restart())

    with pytest.raises(ValueError, match="observed_fencing_counter_after"):
        restart_module.verify_persisted_fenced_restart_bracketed_currentness(
            "receipt.json",
            "head.json",
            "bundle.bin",
            read_fencing_counter=lambda _: next(observations),
            **_kwargs(),
        )


def test_local_identity_drift_fails_before_second_external_read(monkeypatch) -> None:
    read_count = 0
    monkeypatch.setattr(restart_module, "load_fenced_restart_evidence_receipt", lambda *a, **k: _receipt())
    monkeypatch.setattr(
        restart_module,
        "verify_persisted_process_transfer_restart",
        lambda *a, **k: _restart(bundle_sha256="9" * 64),
    )

    def read(_authority_id: str) -> int:
        nonlocal read_count
        read_count += 1
        return 41

    with pytest.raises(ValueError, match="restart bundle_sha256"):
        restart_module.verify_persisted_fenced_restart_bracketed_currentness(
            "receipt.json", "head.json", "bundle.bin", read_fencing_counter=read, **_kwargs()
        )
    assert read_count == 1


def test_second_resolver_failure_is_wrapped_and_grants_no_result(monkeypatch) -> None:
    read_count = 0
    monkeypatch.setattr(restart_module, "load_fenced_restart_evidence_receipt", lambda *a, **k: _receipt())
    monkeypatch.setattr(restart_module, "verify_persisted_process_transfer_restart", lambda *a, **k: _restart())

    def read(_authority_id: str) -> int:
        nonlocal read_count
        read_count += 1
        if read_count == 1:
            return 41
        raise RuntimeError("offline")

    with pytest.raises(ValueError, match="current-counter observation failed"):
        restart_module.verify_persisted_fenced_restart_bracketed_currentness(
            "receipt.json", "head.json", "bundle.bin", read_fencing_counter=read, **_kwargs()
        )
    assert read_count == 2
