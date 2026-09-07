from __future__ import annotations

import hashlib

import pytest

import app.process_transfer_fencing_receipt_persistence as persistence_module
from app.process_transfer_fencing import FencedAuthenticatedProcessTransferRestartVerification
from app.process_transfer_fencing_receipt import encode_fenced_restart_evidence_receipt
from app.process_transfer_fencing_receipt_persistence import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    load_fenced_restart_evidence_receipt,
    persist_fenced_restart_evidence_receipt,
)


def _sha(label: bytes) -> str:
    return hashlib.sha256(label).hexdigest()


def _verification() -> FencedAuthenticatedProcessTransferRestartVerification:
    return FencedAuthenticatedProcessTransferRestartVerification(
        key_id="receiver-key-v1",
        authority_id="receiver-a",
        sequence=7,
        head_sha256=_sha(b"head"),
        bundle_sha256=_sha(b"bundle"),
        migration_id="migration-7",
        session_id="session-7",
        target_candidate_id="generated-index-v7",
        fencing_authority_id="fencing-service-a",
        previous_fencing_counter=41,
        fencing_counter=42,
    )


def _expected() -> dict[str, object]:
    source = _verification()
    return {
        "expected_key_id": source.key_id,
        "expected_authority_id": source.authority_id,
        "expected_sequence": source.sequence,
        "expected_head_sha256": source.head_sha256,
        "expected_bundle_sha256": source.bundle_sha256,
        "expected_migration_id": source.migration_id,
        "expected_session_id": source.session_id,
        "expected_target_candidate_id": source.target_candidate_id,
        "expected_fencing_authority_id": source.fencing_authority_id,
        "expected_previous_fencing_counter": source.previous_fencing_counter,
        "expected_fencing_counter": source.fencing_counter,
    }


def test_persist_and_reload_exact_fenced_receipt_without_authority_escalation(tmp_path) -> None:
    receipt = encode_fenced_restart_evidence_receipt(_verification())
    path = tmp_path / "fenced-restart.receipt"

    evidence = persist_fenced_restart_evidence_receipt(path, receipt, **_expected())
    replay = load_fenced_restart_evidence_receipt(path, **_expected())

    assert path.read_bytes() == receipt
    assert evidence.receipt_sha256 == hashlib.sha256(receipt).hexdigest()
    assert replay.receipt_sha256 == evidence.receipt_sha256
    assert evidence.pre_write_replay_verified is True
    assert evidence.file_fsync_completed is True
    assert evidence.atomic_name_replace_completed is True
    assert evidence.post_write_replay_verified is True
    assert evidence.evidence_state == EVIDENCE_STATE
    assert evidence.automatic_control_allowed is False
    assert evidence.activation_allowed is False
    assert evidence.traffic_switching_allowed is False


def test_pre_write_identity_failure_preserves_existing_target(tmp_path) -> None:
    receipt = encode_fenced_restart_evidence_receipt(_verification())
    path = tmp_path / "fenced-restart.receipt"
    path.write_bytes(b"existing-receipt")
    expected = _expected()
    expected["expected_head_sha256"] = _sha(b"wrong-head")

    with pytest.raises(ValueError, match="head_sha256 does not match expected identity"):
        persist_fenced_restart_evidence_receipt(path, receipt, **expected)

    assert path.read_bytes() == b"existing-receipt"


def test_replace_failure_preserves_existing_target_and_cleans_staged_file(tmp_path, monkeypatch) -> None:
    receipt = encode_fenced_restart_evidence_receipt(_verification())
    path = tmp_path / "fenced-restart.receipt"
    path.write_bytes(b"existing-receipt")

    def fail_replace(source, destination) -> None:
        raise OSError("injected replace failure")

    monkeypatch.setattr(persistence_module.os, "replace", fail_replace)

    with pytest.raises(OSError, match="injected replace failure"):
        persist_fenced_restart_evidence_receipt(path, receipt, **_expected())

    assert path.read_bytes() == b"existing-receipt"
    assert list(tmp_path.glob(".fenced-restart.receipt.*.tmp")) == []


def test_load_rejects_tampered_persisted_receipt(tmp_path) -> None:
    receipt = encode_fenced_restart_evidence_receipt(_verification())
    path = tmp_path / "fenced-restart.receipt"
    persist_fenced_restart_evidence_receipt(path, receipt, **_expected())
    path.write_bytes(receipt[:-1] + b" ")

    with pytest.raises(ValueError, match="receipt bytes are not canonical"):
        load_fenced_restart_evidence_receipt(path, **_expected())


def test_missing_parent_fails_after_receipt_replay_without_creating_directories(tmp_path) -> None:
    receipt = encode_fenced_restart_evidence_receipt(_verification())
    path = tmp_path / "missing" / "fenced-restart.receipt"

    with pytest.raises(FileNotFoundError, match="parent directory does not exist"):
        persist_fenced_restart_evidence_receipt(path, receipt, **_expected())

    assert not path.parent.exists()


def test_truth_boundary_denies_freshness_cutover_and_durability_claims() -> None:
    assert "does not repeat the external fencing compare-and-advance operation" in TRUTH_BOUNDARY
    assert "prove the fencing generation is still current" in TRUTH_BOUNDARY
    assert "guarantee directory-entry or power-loss durability" in TRUTH_BOUNDARY
    assert "authorize activation or traffic switching" in TRUTH_BOUNDARY
