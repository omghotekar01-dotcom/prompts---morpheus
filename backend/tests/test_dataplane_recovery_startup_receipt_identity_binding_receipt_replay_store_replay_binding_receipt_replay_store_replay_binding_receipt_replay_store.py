from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay import (
    EVIDENCE_STATE as P90_EVIDENCE_STATE,
    RecoveryStartupReplayRetainedIdentityBindingReceiptReplayEvidence,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    store_recovery_startup_replay_retained_identity_binding_receipt_replay_identity,
)


def _evidence() -> RecoveryStartupReplayRetainedIdentityBindingReceiptReplayEvidence:
    return RecoveryStartupReplayRetainedIdentityBindingReceiptReplayEvidence(
        sequence=23,
        lineage_sha256="a" * 64,
        binding_receipt_payload_sha256="b" * 64,
        binding_receipt_payload_size_bytes=101,
        receipt_identity_binding_sha256="c" * 64,
        retained_identity_payload_sha256="d" * 64,
        retained_identity_payload_size_bytes=202,
        replay_stored_identity_binding_sha256="e" * 64,
        replay_binding_receipt_payload_sha256="f" * 64,
        replay_binding_receipt_payload_size_bytes=303,
        retained_replay_identity_payload_sha256="1" * 64,
        retained_replay_identity_payload_size_bytes=404,
        replay_retained_identity_binding_sha256="2" * 64,
        replay_retained_identity_binding_receipt_payload_sha256="3" * 64,
        replay_retained_identity_binding_receipt_payload_size_bytes=505,
        expected_payload_identity_verified=True,
        canonical_receipt_verified=True,
        dependency_state_verified=True,
        replay_retained_identity_binding_recomputed_verified=True,
        p88_evidence_state="P88_STATE_IS_OPAQUE_TO_P91",
    )


def _canonical(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def test_p91_persists_minimal_canonical_p90_replay_identity(tmp_path) -> None:
    destination = tmp_path / "nested" / "p90.identity.json"
    stored = store_recovery_startup_replay_retained_identity_binding_receipt_replay_identity(
        _evidence(), destination_path=destination
    )

    raw = destination.read_bytes()
    decoded = json.loads(raw)
    assert raw == _canonical(decoded)
    assert decoded == {
        "binding_receipt_payload_sha256": "b" * 64,
        "binding_receipt_payload_size_bytes": 101,
        "lineage_sha256": "a" * 64,
        "p90_evidence_state": P90_EVIDENCE_STATE,
        "receipt_identity_binding_sha256": "c" * 64,
        "replay_binding_receipt_payload_sha256": "f" * 64,
        "replay_binding_receipt_payload_size_bytes": 303,
        "replay_retained_identity_binding_receipt_payload_sha256": "3" * 64,
        "replay_retained_identity_binding_receipt_payload_size_bytes": 505,
        "replay_retained_identity_binding_sha256": "2" * 64,
        "replay_stored_identity_binding_sha256": "e" * 64,
        "retained_identity_payload_sha256": "d" * 64,
        "retained_identity_payload_size_bytes": 202,
        "retained_replay_identity_payload_sha256": "1" * 64,
        "retained_replay_identity_payload_size_bytes": 404,
        "sequence": 23,
    }
    assert stored.stored_payload_sha256 == hashlib.sha256(raw).hexdigest()
    assert stored.stored_payload_size_bytes == len(raw)
    assert stored.destination_path == str(destination)
    assert stored.evidence_state == EVIDENCE_STATE
    assert stored.p90_evidence_state_verified is True
    assert stored.p90_verification_flags_verified is True
    assert stored.exact_readback_verified is True
    assert stored.automatic_control_allowed is False


def test_p91_replaces_existing_record_without_temp_residue(tmp_path) -> None:
    destination = tmp_path / "p90.identity.json"
    destination.write_bytes(b"old")
    store_recovery_startup_replay_retained_identity_binding_receipt_replay_identity(
        _evidence(), destination_path=destination
    )
    assert destination.read_bytes() != b"old"
    assert list(tmp_path.glob(".p90.identity.json.*.tmp")) == []


@pytest.mark.parametrize(
    "flag",
    [
        "expected_payload_identity_verified",
        "canonical_receipt_verified",
        "dependency_state_verified",
        "replay_retained_identity_binding_recomputed_verified",
    ],
)
def test_p91_rejects_weakened_p90_verification_contract(tmp_path, flag) -> None:
    with pytest.raises(ValueError, match="verification flags are incomplete"):
        store_recovery_startup_replay_retained_identity_binding_receipt_replay_identity(
            replace(_evidence(), **{flag: False}), destination_path=tmp_path / "identity.json"
        )


def test_p91_rejects_p90_state_or_control_escalation(tmp_path) -> None:
    with pytest.raises(ValueError, match="evidence state is incompatible"):
        store_recovery_startup_replay_retained_identity_binding_receipt_replay_identity(
            replace(_evidence(), evidence_state="DRIFTED"), destination_path=tmp_path / "identity.json"
        )
    with pytest.raises(ValueError, match="must not grant automatic-control authority"):
        store_recovery_startup_replay_retained_identity_binding_receipt_replay_identity(
            replace(_evidence(), automatic_control_allowed=True), destination_path=tmp_path / "identity.json"
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sequence", True),
        ("sequence", 0),
        ("lineage_sha256", "A" * 64),
        ("binding_receipt_payload_size_bytes", 0),
        ("receipt_identity_binding_sha256", "x" * 64),
        ("retained_identity_payload_size_bytes", -1),
        ("replay_binding_receipt_payload_size_bytes", True),
        ("retained_replay_identity_payload_size_bytes", 0),
        ("replay_retained_identity_binding_sha256", "2" * 63),
        ("replay_retained_identity_binding_receipt_payload_sha256", "g" * 64),
        ("replay_retained_identity_binding_receipt_payload_size_bytes", 0),
    ],
)
def test_p91_rejects_invalid_p90_semantic_identity(tmp_path, field, value) -> None:
    with pytest.raises(ValueError):
        store_recovery_startup_replay_retained_identity_binding_receipt_replay_identity(
            replace(_evidence(), **{field: value}), destination_path=tmp_path / "identity.json"
        )


def test_p91_stored_identity_changes_with_new_p90_outer_receipt_identity(tmp_path) -> None:
    first = store_recovery_startup_replay_retained_identity_binding_receipt_replay_identity(
        _evidence(), destination_path=tmp_path / "first.json"
    )
    second = store_recovery_startup_replay_retained_identity_binding_receipt_replay_identity(
        replace(
            _evidence(),
            replay_retained_identity_binding_receipt_payload_sha256="4" * 64,
            replay_retained_identity_binding_receipt_payload_size_bytes=506,
        ),
        destination_path=tmp_path / "second.json",
    )
    assert first.stored_payload_sha256 != second.stored_payload_sha256
    assert first.stored_payload_size_bytes == second.stored_payload_size_bytes


def test_p91_rejects_incompatible_input_type(tmp_path) -> None:
    with pytest.raises(ValueError, match="incompatible type"):
        store_recovery_startup_replay_retained_identity_binding_receipt_replay_identity(  # type: ignore[arg-type]
            object(), destination_path=tmp_path / "identity.json"
        )


def test_p91_exported_evidence_and_truth_boundary_remain_non_authoritative(tmp_path) -> None:
    exported = store_recovery_startup_replay_retained_identity_binding_receipt_replay_identity(
        _evidence(), destination_path=tmp_path / "identity.json"
    ).as_dict()
    assert exported["p90_evidence_state_verified"] is True
    assert exported["p90_verification_flags_verified"] is True
    assert exported["exact_readback_verified"] is True
    assert exported["automatic_control_allowed"] is False
    assert exported["evidence_state"] == EVIDENCE_STATE
    assert exported["truth_boundary"] == TRUTH_BOUNDARY

    lower = TRUTH_BOUNDARY.lower()
    for phrase in (
        "does not authenticate",
        "freshness",
        "coordinated replacement",
        "authorize startup or mutation",
        "production readiness",
        "benchmark evidence",
        "novelty evidence",
        "automatic-control authority",
    ):
        assert phrase in lower
