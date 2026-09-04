from __future__ import annotations

from dataclasses import replace

import pytest

from app.dataplane_recovery_startup_receipt_identity_replay import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    replay_recovery_startup_receipt_identity,
)
from app.dataplane_recovery_startup_receipt_identity_store import (
    RecoveryStartupReceiptIdentityStoreEvidence,
    store_recovery_startup_receipt_identity,
)
from app.dataplane_recovery_startup_receipt_replay import (
    RecoveryStartupAdmissionReceiptReplayEvidence,
)


def _p75() -> RecoveryStartupAdmissionReceiptReplayEvidence:
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


def _stored(tmp_path) -> tuple[RecoveryStartupReceiptIdentityStoreEvidence, object]:
    path = tmp_path / "startup-receipt-head.json"
    evidence = store_recovery_startup_receipt_identity(_p75(), destination_path=path)
    return evidence, path


def test_p77_replays_exact_p76_identity_record(tmp_path) -> None:
    stored, path = _stored(tmp_path)

    replay = replay_recovery_startup_receipt_identity(stored, source_path=path)

    assert replay.evidence_state == EVIDENCE_STATE
    assert replay.sequence == stored.sequence
    assert replay.lineage_sha256 == stored.lineage_sha256
    assert replay.receipt_payload_sha256 == stored.receipt_payload_sha256
    assert replay.receipt_payload_size_bytes == stored.receipt_payload_size_bytes
    assert replay.admission_binding_sha256 == stored.admission_binding_sha256
    assert replay.stored_payload_sha256 == stored.stored_payload_sha256
    assert replay.stored_payload_size_bytes == stored.stored_payload_size_bytes
    assert replay.expected_payload_identity_verified is True
    assert replay.canonical_record_verified is True
    assert replay.semantic_identity_verified is True
    assert replay.automatic_control_allowed is False


def test_p77_defaults_to_p76_destination_path(tmp_path) -> None:
    stored, path = _stored(tmp_path)

    replay = replay_recovery_startup_receipt_identity(stored)

    assert replay.source_path == str(path)


@pytest.mark.parametrize(
    "mutation",
    [
        {"evidence_state": "WRONG"},
        {"automatic_control_allowed": True},
        {"p75_evidence_state_verified": False},
        {"p75_verification_flags_verified": False},
        {"exact_readback_verified": False},
        {"sequence": True},
        {"sequence": 0},
        {"lineage_sha256": "A" * 64},
        {"receipt_payload_sha256": "g" * 64},
        {"receipt_payload_size_bytes": 0},
        {"admission_binding_sha256": "0" * 63},
        {"stored_payload_sha256": "0" * 63},
        {"stored_payload_size_bytes": 0},
    ],
)
def test_p77_rejects_incompatible_or_weakened_p76_evidence(tmp_path, mutation) -> None:
    stored, path = _stored(tmp_path)

    with pytest.raises(ValueError):
        replay_recovery_startup_receipt_identity(
            replace(stored, **mutation), source_path=path
        )


def test_p77_rejects_non_p76_objects(tmp_path) -> None:
    with pytest.raises(ValueError, match="incompatible type"):
        replay_recovery_startup_receipt_identity(
            object(),  # type: ignore[arg-type]
            source_path=tmp_path / "head.json",
        )


def test_p77_rejects_post_p76_byte_drift(tmp_path) -> None:
    stored, path = _stored(tmp_path)
    raw = path.read_bytes()
    path.write_bytes(raw[:-1] + (b"X" if raw[-1:] != b"X" else b"Y"))

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        replay_recovery_startup_receipt_identity(stored, source_path=path)


def test_p77_rejects_post_p76_size_drift(tmp_path) -> None:
    stored, path = _stored(tmp_path)
    path.write_bytes(path.read_bytes() + b" ")

    with pytest.raises(ValueError, match="byte length mismatch"):
        replay_recovery_startup_receipt_identity(stored, source_path=path)


def test_p77_rejects_missing_record(tmp_path) -> None:
    stored, path = _stored(tmp_path)
    path.unlink()

    with pytest.raises(FileNotFoundError):
        replay_recovery_startup_receipt_identity(stored, source_path=path)


def test_p77_is_local_replay_verification_not_freshness_or_startup_authority(tmp_path) -> None:
    stored, path = _stored(tmp_path)
    replay = replay_recovery_startup_receipt_identity(stored, source_path=path)

    path.write_bytes(b"replaced-after-verification")

    assert replay.automatic_control_allowed is False
    assert "historical" in TRUTH_BOUNDARY or "during this call" in TRUTH_BOUNDARY
    assert "freshness" in TRUTH_BOUNDARY
    assert "rollback/replay" in TRUTH_BOUNDARY
    assert "authorize startup" in TRUTH_BOUNDARY
    assert "benchmark" in TRUTH_BOUNDARY
