from __future__ import annotations

import hashlib
import json

import pytest

from app.process_transfer_fencing import FencedAuthenticatedProcessTransferRestartVerification
from app.process_transfer_fencing_receipt import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    encode_fenced_restart_evidence_receipt,
    verify_fenced_restart_evidence_receipt,
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


def test_receipt_round_trip_binds_exact_fenced_restart_evidence_without_authority_escalation() -> None:
    receipt = encode_fenced_restart_evidence_receipt(_verification())
    replay = verify_fenced_restart_evidence_receipt(receipt, **_expected())

    assert replay.receipt_sha256 == hashlib.sha256(receipt).hexdigest()
    assert replay.canonical_encoding_verified is True
    assert replay.exact_identity_binding_verified is True
    assert replay.evidence_state == EVIDENCE_STATE
    assert replay.automatic_control_allowed is False
    assert replay.activation_allowed is False
    assert replay.traffic_switching_allowed is False


def test_receipt_encoding_is_deterministic_and_canonical() -> None:
    first = encode_fenced_restart_evidence_receipt(_verification())
    second = encode_fenced_restart_evidence_receipt(_verification())

    assert first == second
    assert first.endswith(b"\n")
    assert json.loads(first) ["fencing_counter"] == 42


def test_receipt_replay_rejects_identity_drift() -> None:
    receipt = encode_fenced_restart_evidence_receipt(_verification())
    expected = _expected()
    expected["expected_head_sha256"] = _sha(b"different-head")

    with pytest.raises(ValueError, match="head_sha256 does not match expected identity"):
        verify_fenced_restart_evidence_receipt(receipt, **expected)


def test_receipt_replay_rejects_noncanonical_or_tampered_authority_fields() -> None:
    receipt = encode_fenced_restart_evidence_receipt(_verification())
    payload = json.loads(receipt)
    payload["activation_allowed"] = True
    tampered = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()

    with pytest.raises(ValueError, match="activation_allowed must be false"):
        verify_fenced_restart_evidence_receipt(tampered, **_expected())

    noncanonical = json.dumps(json.loads(receipt), indent=2).encode()
    with pytest.raises(ValueError, match="receipt bytes are not canonical"):
        verify_fenced_restart_evidence_receipt(noncanonical, **_expected())


def test_receipt_rejects_noncontiguous_fencing_evidence() -> None:
    source = _verification()
    invalid = FencedAuthenticatedProcessTransferRestartVerification(
        key_id=source.key_id,
        authority_id=source.authority_id,
        sequence=source.sequence,
        head_sha256=source.head_sha256,
        bundle_sha256=source.bundle_sha256,
        migration_id=source.migration_id,
        session_id=source.session_id,
        target_candidate_id=source.target_candidate_id,
        fencing_authority_id=source.fencing_authority_id,
        previous_fencing_counter=41,
        fencing_counter=43,
    )

    with pytest.raises(ValueError, match="fencing_counter must be exactly"):
        encode_fenced_restart_evidence_receipt(invalid)


def test_truth_boundary_explicitly_denies_cutover_and_external_service_proof() -> None:
    assert "does not repeat the external compare-and-advance operation" in TRUTH_BOUNDARY
    assert "prove that its counter is still current" in TRUTH_BOUNDARY
    assert "activation or traffic-switching authority" in TRUTH_BOUNDARY
