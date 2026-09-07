from __future__ import annotations

import hashlib

import pytest

import app.process_transfer_fencing_receipt_restart_bracketed_evidence_persistence as persistence_module
from app.process_transfer_fencing_receipt_restart import BracketedFencedRestartCurrentnessVerification
from app.process_transfer_fencing_receipt_restart_bracketed_evidence import (
    encode_bracketed_restart_observation_receipt,
)
from app.process_transfer_fencing_receipt_restart_bracketed_evidence_persistence import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    load_bracketed_restart_observation_receipt,
    persist_bracketed_restart_observation_receipt,
)


HEAD = "1" * 64
BUNDLE = "2" * 64
SOURCE_RECEIPT = "3" * 64


def _verification(**overrides) -> BracketedFencedRestartCurrentnessVerification:
    values = dict(
        receipt_sha256=SOURCE_RECEIPT,
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
        observed_fencing_counter_before=41,
        observed_fencing_counter_after=41,
    )
    values.update(overrides)
    return BracketedFencedRestartCurrentnessVerification(**values)


def _expected() -> dict[str, object]:
    return {
        "expected_source_receipt_sha256": SOURCE_RECEIPT,
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
    }


def test_persist_and_reload_exact_bracketed_receipt_without_authority_escalation(tmp_path) -> None:
    receipt = encode_bracketed_restart_observation_receipt(_verification())
    path = tmp_path / "bracketed-restart-observation.receipt"

    evidence = persist_bracketed_restart_observation_receipt(path, receipt, **_expected())
    replay = load_bracketed_restart_observation_receipt(path, **_expected())

    assert path.read_bytes() == receipt
    assert evidence.evidence_receipt_sha256 == hashlib.sha256(receipt).hexdigest()
    assert replay.evidence_receipt_sha256 == evidence.evidence_receipt_sha256
    assert evidence.source_receipt_sha256 == SOURCE_RECEIPT
    assert evidence.observed_fencing_counter_before == 41
    assert evidence.observed_fencing_counter_after == 41
    assert evidence.pre_write_replay_verified is True
    assert evidence.file_fsync_completed is True
    assert evidence.atomic_name_replace_completed is True
    assert evidence.post_write_replay_verified is True
    assert evidence.historical_observation_binding_only is True
    assert evidence.evidence_state == EVIDENCE_STATE
    assert evidence.automatic_control_allowed is False
    assert evidence.activation_allowed is False
    assert evidence.traffic_switching_allowed is False


def test_pre_write_identity_failure_preserves_existing_target(tmp_path) -> None:
    receipt = encode_bracketed_restart_observation_receipt(_verification())
    path = tmp_path / "bracketed-restart-observation.receipt"
    path.write_bytes(b"existing-receipt")
    expected = _expected()
    expected["expected_key_id"] = "key-2"

    with pytest.raises(ValueError, match="key_id does not match expected identity"):
        persist_bracketed_restart_observation_receipt(path, receipt, **expected)

    assert path.read_bytes() == b"existing-receipt"


def test_replace_failure_preserves_existing_target_and_cleans_staged_file(tmp_path, monkeypatch) -> None:
    receipt = encode_bracketed_restart_observation_receipt(_verification())
    path = tmp_path / "bracketed-restart-observation.receipt"
    path.write_bytes(b"existing-receipt")

    def fail_replace(source, destination) -> None:
        raise OSError("injected replace failure")

    monkeypatch.setattr(persistence_module.os, "replace", fail_replace)

    with pytest.raises(OSError, match="injected replace failure"):
        persist_bracketed_restart_observation_receipt(path, receipt, **_expected())

    assert path.read_bytes() == b"existing-receipt"
    assert list(tmp_path.glob(".bracketed-restart-observation.receipt.*.tmp")) == []


def test_load_rejects_tampered_persisted_receipt(tmp_path) -> None:
    receipt = encode_bracketed_restart_observation_receipt(_verification())
    path = tmp_path / "bracketed-restart-observation.receipt"
    persist_bracketed_restart_observation_receipt(path, receipt, **_expected())
    path.write_bytes(receipt[:-1] + b" ")

    with pytest.raises(ValueError, match="bytes are not canonical"):
        load_bracketed_restart_observation_receipt(path, **_expected())


def test_missing_parent_fails_after_receipt_replay_without_creating_directories(tmp_path) -> None:
    receipt = encode_bracketed_restart_observation_receipt(_verification())
    path = tmp_path / "missing" / "bracketed-restart-observation.receipt"

    with pytest.raises(FileNotFoundError, match="parent directory does not exist"):
        persist_bracketed_restart_observation_receipt(path, receipt, **_expected())

    assert not path.parent.exists()


def test_truth_boundary_denies_freshness_cutover_and_durability_claims() -> None:
    assert "does not call the external fencing authority" in TRUTH_BOUNDARY
    assert "prove the fencing generation is current" in TRUTH_BOUNDARY
    assert "guarantee directory-entry or power-loss durability" in TRUTH_BOUNDARY
    assert "authorize activation, automatic control or traffic switching" in TRUTH_BOUNDARY
    assert "historical evidence only" in TRUTH_BOUNDARY
