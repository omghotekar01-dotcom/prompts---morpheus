from dataclasses import replace
import hashlib
import json

import pytest

from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding import (
    EVIDENCE_STATE as P83_EVIDENCE_STATE,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay import (
    EVIDENCE_STATE as P85_EVIDENCE_STATE,
    RecoveryStartupReplayStoredIdentityBindingReceiptReplayEvidence,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store import (
    EVIDENCE_STATE as P86_EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    store_recovery_startup_replay_stored_identity_binding_receipt_replay_identity,
)


def _sha(ch: str) -> str:
    return ch * 64


def _valid_p85() -> RecoveryStartupReplayStoredIdentityBindingReceiptReplayEvidence:
    return RecoveryStartupReplayStoredIdentityBindingReceiptReplayEvidence(
        sequence=11,
        lineage_sha256=_sha("a"),
        binding_receipt_payload_sha256=_sha("b"),
        binding_receipt_payload_size_bytes=201,
        receipt_identity_binding_sha256=_sha("c"),
        retained_identity_payload_sha256=_sha("d"),
        retained_identity_payload_size_bytes=202,
        replay_stored_identity_binding_sha256=_sha("e"),
        replay_binding_receipt_payload_sha256=_sha("f"),
        replay_binding_receipt_payload_size_bytes=203,
        expected_payload_identity_verified=True,
        canonical_receipt_verified=True,
        dependency_state_verified=True,
        replay_stored_identity_binding_recomputed_verified=True,
        p83_evidence_state=P83_EVIDENCE_STATE,
    )


def test_p86_stores_minimal_canonical_p85_identity(tmp_path) -> None:
    destination = tmp_path / "state" / "p85-replay.json"
    evidence = store_recovery_startup_replay_stored_identity_binding_receipt_replay_identity(
        _valid_p85(), destination_path=destination
    )

    stored = destination.read_bytes()
    decoded = json.loads(stored)
    assert stored == json.dumps(decoded, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    assert decoded == {
        "binding_receipt_payload_sha256": _sha("b"),
        "binding_receipt_payload_size_bytes": 201,
        "lineage_sha256": _sha("a"),
        "p85_evidence_state": P85_EVIDENCE_STATE,
        "receipt_identity_binding_sha256": _sha("c"),
        "replay_binding_receipt_payload_sha256": _sha("f"),
        "replay_binding_receipt_payload_size_bytes": 203,
        "replay_stored_identity_binding_sha256": _sha("e"),
        "retained_identity_payload_sha256": _sha("d"),
        "retained_identity_payload_size_bytes": 202,
        "sequence": 11,
    }
    assert evidence.stored_payload_sha256 == hashlib.sha256(stored).hexdigest()
    assert evidence.stored_payload_size_bytes == len(stored)
    assert evidence.p85_evidence_state_verified is True
    assert evidence.p85_verification_flags_verified is True
    assert evidence.exact_readback_verified is True
    assert evidence.evidence_state == P86_EVIDENCE_STATE
    assert evidence.automatic_control_allowed is False


def test_p86_replaces_existing_record_without_temp_residue(tmp_path) -> None:
    destination = tmp_path / "p85-replay.json"
    destination.write_text("old")
    store_recovery_startup_replay_stored_identity_binding_receipt_replay_identity(
        _valid_p85(), destination_path=destination
    )
    assert destination.read_text() != "old"
    assert list(tmp_path.glob(f".{destination.name}.*.tmp")) == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("sequence", 12),
        ("lineage_sha256", _sha("1")),
        ("binding_receipt_payload_sha256", _sha("2")),
        ("binding_receipt_payload_size_bytes", 204),
        ("receipt_identity_binding_sha256", _sha("3")),
        ("retained_identity_payload_sha256", _sha("4")),
        ("retained_identity_payload_size_bytes", 205),
        ("replay_stored_identity_binding_sha256", _sha("5")),
        ("replay_binding_receipt_payload_sha256", _sha("6")),
        ("replay_binding_receipt_payload_size_bytes", 206),
    ],
)
def test_p86_stored_identity_binds_each_retained_p85_field(tmp_path, field: str, value) -> None:
    baseline = store_recovery_startup_replay_stored_identity_binding_receipt_replay_identity(
        _valid_p85(), destination_path=tmp_path / "baseline.json"
    )
    changed = store_recovery_startup_replay_stored_identity_binding_receipt_replay_identity(
        replace(_valid_p85(), **{field: value}), destination_path=tmp_path / "changed.json"
    )
    assert changed.stored_payload_sha256 != baseline.stored_payload_sha256


@pytest.mark.parametrize(
    "flag",
    [
        "expected_payload_identity_verified",
        "canonical_receipt_verified",
        "dependency_state_verified",
        "replay_stored_identity_binding_recomputed_verified",
    ],
)
def test_p86_rejects_weakened_p85_verification_flags(tmp_path, flag: str) -> None:
    with pytest.raises(ValueError, match="verification flags are incomplete"):
        store_recovery_startup_replay_stored_identity_binding_receipt_replay_identity(
            replace(_valid_p85(), **{flag: False}), destination_path=tmp_path / "p85.json"
        )


def test_p86_rejects_incompatible_state_and_control_escalation(tmp_path) -> None:
    with pytest.raises(ValueError, match="state is incompatible"):
        store_recovery_startup_replay_stored_identity_binding_receipt_replay_identity(
            replace(_valid_p85(), evidence_state="OTHER"), destination_path=tmp_path / "p85.json"
        )
    with pytest.raises(ValueError, match="must not grant automatic-control authority"):
        store_recovery_startup_replay_stored_identity_binding_receipt_replay_identity(
            replace(_valid_p85(), automatic_control_allowed=True), destination_path=tmp_path / "p85.json"
        )


@pytest.mark.parametrize("sequence", [0, -1, True])
def test_p86_rejects_invalid_sequence(tmp_path, sequence) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        store_recovery_startup_replay_stored_identity_binding_receipt_replay_identity(
            replace(_valid_p85(), sequence=sequence), destination_path=tmp_path / "p85.json"
        )


def test_p86_rejects_malformed_hash_and_size(tmp_path) -> None:
    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        store_recovery_startup_replay_stored_identity_binding_receipt_replay_identity(
            replace(_valid_p85(), replay_binding_receipt_payload_sha256="BAD"), destination_path=tmp_path / "p85.json"
        )
    with pytest.raises(ValueError, match="positive integer"):
        store_recovery_startup_replay_stored_identity_binding_receipt_replay_identity(
            replace(_valid_p85(), replay_binding_receipt_payload_size_bytes=0), destination_path=tmp_path / "p85.json"
        )


def test_p86_rejects_non_p85_object(tmp_path) -> None:
    with pytest.raises(ValueError, match="incompatible type"):
        store_recovery_startup_replay_stored_identity_binding_receipt_replay_identity(
            object(), destination_path=tmp_path / "p85.json"
        )


def test_p86_truth_boundary_remains_local_historical_evidence() -> None:
    boundary = TRUTH_BOUNDARY.lower()
    for phrase in (
        "local historical evidence",
        "not an authenticated",
        "freshness",
        "rollback",
        "authorize startup",
        "production readiness",
        "benchmark evidence",
        "novelty evidence",
        "automatic-control authority",
    ):
        assert phrase in boundary
