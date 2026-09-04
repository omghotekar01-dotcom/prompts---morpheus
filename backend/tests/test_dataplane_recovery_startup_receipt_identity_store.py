from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.dataplane_recovery_startup_receipt_identity_store import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    store_recovery_startup_receipt_identity,
)
from app.dataplane_recovery_startup_receipt_replay import (
    EVIDENCE_STATE as P75_EVIDENCE_STATE,
    RecoveryStartupAdmissionReceiptReplayEvidence,
)


def _evidence() -> RecoveryStartupAdmissionReceiptReplayEvidence:
    return RecoveryStartupAdmissionReceiptReplayEvidence(
        sequence=7,
        lineage_sha256="a" * 64,
        admission_binding_sha256="b" * 64,
        receipt_payload_sha256="c" * 64,
        receipt_payload_size_bytes=321,
        expected_payload_identity_verified=True,
        canonical_receipt_verified=True,
        admission_binding_recomputed_verified=True,
        dependency_states_verified=True,
    )


def test_p76_stores_minimal_canonical_p75_identity(tmp_path) -> None:
    destination = tmp_path / "startup-receipt-head.json"
    evidence = store_recovery_startup_receipt_identity(
        _evidence(), destination_path=destination
    )

    expected_payload = {
        "admission_binding_sha256": "b" * 64,
        "lineage_sha256": "a" * 64,
        "p75_evidence_state": P75_EVIDENCE_STATE,
        "receipt_payload_sha256": "c" * 64,
        "receipt_payload_size_bytes": 321,
        "sequence": 7,
    }
    expected = json.dumps(
        expected_payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")

    assert destination.read_bytes() == expected
    assert evidence.evidence_state == EVIDENCE_STATE
    assert evidence.stored_payload_sha256 == hashlib.sha256(expected).hexdigest()
    assert evidence.stored_payload_size_bytes == len(expected)
    assert evidence.p75_evidence_state_verified is True
    assert evidence.p75_verification_flags_verified is True
    assert evidence.exact_readback_verified is True
    assert evidence.automatic_control_allowed is False
    assert evidence.as_dict()["truth_boundary"] == TRUTH_BOUNDARY


def test_p76_replaces_existing_identity_without_temp_residue(tmp_path) -> None:
    destination = tmp_path / "startup-receipt-head.json"
    destination.write_bytes(b"old")

    store_recovery_startup_receipt_identity(_evidence(), destination_path=destination)

    assert destination.read_bytes() != b"old"
    assert list(tmp_path.glob(".startup-receipt-head.json.*.tmp")) == []


@pytest.mark.parametrize(
    "mutation",
    [
        {"evidence_state": "WRONG"},
        {"automatic_control_allowed": True},
        {"expected_payload_identity_verified": False},
        {"canonical_receipt_verified": False},
        {"admission_binding_recomputed_verified": False},
        {"dependency_states_verified": False},
        {"sequence": True},
        {"sequence": 0},
        {"lineage_sha256": "A" * 64},
        {"admission_binding_sha256": "0" * 63},
        {"receipt_payload_sha256": "g" * 64},
        {"receipt_payload_size_bytes": 0},
    ],
)
def test_p76_rejects_incompatible_or_weakened_p75_evidence(tmp_path, mutation) -> None:
    with pytest.raises(ValueError):
        store_recovery_startup_receipt_identity(
            replace(_evidence(), **mutation),
            destination_path=tmp_path / "head.json",
        )


def test_p76_rejects_non_p75_objects(tmp_path) -> None:
    with pytest.raises(ValueError, match="incompatible type"):
        store_recovery_startup_receipt_identity(
            object(),  # type: ignore[arg-type]
            destination_path=tmp_path / "head.json",
        )


def test_p76_creates_parent_directory_and_emits_deterministic_identity(tmp_path) -> None:
    first_path = tmp_path / "a" / "head.json"
    second_path = tmp_path / "b" / "head.json"

    first = store_recovery_startup_receipt_identity(_evidence(), destination_path=first_path)
    second = store_recovery_startup_receipt_identity(_evidence(), destination_path=second_path)

    assert first_path.read_bytes() == second_path.read_bytes()
    assert first.stored_payload_sha256 == second.stored_payload_sha256
    assert first.stored_payload_size_bytes == second.stored_payload_size_bytes


def test_p76_is_local_retention_not_freshness_authentication_or_startup_authority(tmp_path) -> None:
    destination = tmp_path / "head.json"
    old = store_recovery_startup_receipt_identity(_evidence(), destination_path=destination)

    repeated = store_recovery_startup_receipt_identity(_evidence(), destination_path=destination)

    assert old.stored_payload_sha256 == repeated.stored_payload_sha256
    assert repeated.automatic_control_allowed is False
    assert "not an authenticated" in TRUTH_BOUNDARY
    assert "freshness" in TRUTH_BOUNDARY
    assert "rollback/replay" in TRUTH_BOUNDARY
    assert "authorize startup" in TRUTH_BOUNDARY
    assert "benchmark" in TRUTH_BOUNDARY
