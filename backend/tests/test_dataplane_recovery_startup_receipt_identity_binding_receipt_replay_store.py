from dataclasses import replace
import hashlib
import json

import pytest

from app.dataplane_recovery_startup_receipt_identity_binding import EVIDENCE_STATE as P78_EVIDENCE_STATE
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay import (
    EVIDENCE_STATE as P80_EVIDENCE_STATE,
    RecoveryStartupStoredReceiptBindingReceiptReplayEvidence,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store import (
    EVIDENCE_STATE as P81_EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    store_recovery_startup_stored_receipt_binding_receipt_replay_identity,
)


def _sha(ch: str) -> str:
    return ch * 64


def _valid_p80() -> RecoveryStartupStoredReceiptBindingReceiptReplayEvidence:
    return RecoveryStartupStoredReceiptBindingReceiptReplayEvidence(
        sequence=7,
        lineage_sha256=_sha("a"),
        receipt_payload_sha256=_sha("b"),
        receipt_payload_size_bytes=101,
        admission_binding_sha256=_sha("c"),
        stored_identity_payload_sha256=_sha("d"),
        stored_identity_payload_size_bytes=102,
        receipt_identity_binding_sha256=_sha("e"),
        binding_receipt_payload_sha256=_sha("f"),
        binding_receipt_payload_size_bytes=103,
        expected_payload_identity_verified=True,
        canonical_receipt_verified=True,
        dependency_state_verified=True,
        receipt_identity_binding_recomputed_verified=True,
        p78_evidence_state=P78_EVIDENCE_STATE,
    )


def test_p81_stores_minimal_canonical_p80_identity(tmp_path) -> None:
    destination = tmp_path / "state" / "p80-replay.json"
    evidence = store_recovery_startup_stored_receipt_binding_receipt_replay_identity(
        _valid_p80(), destination_path=destination
    )

    stored = destination.read_bytes()
    decoded = json.loads(stored)
    assert stored == json.dumps(decoded, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    assert decoded == {
        "binding_receipt_payload_sha256": _sha("f"),
        "binding_receipt_payload_size_bytes": 103,
        "lineage_sha256": _sha("a"),
        "p80_evidence_state": P80_EVIDENCE_STATE,
        "receipt_identity_binding_sha256": _sha("e"),
        "sequence": 7,
    }
    assert evidence.stored_payload_sha256 == hashlib.sha256(stored).hexdigest()
    assert evidence.stored_payload_size_bytes == len(stored)
    assert evidence.p80_evidence_state_verified is True
    assert evidence.p80_verification_flags_verified is True
    assert evidence.exact_readback_verified is True
    assert evidence.evidence_state == P81_EVIDENCE_STATE
    assert evidence.automatic_control_allowed is False


def test_p81_replaces_existing_record_without_temp_residue(tmp_path) -> None:
    destination = tmp_path / "p80-replay.json"
    destination.write_text("old")
    store_recovery_startup_stored_receipt_binding_receipt_replay_identity(
        _valid_p80(), destination_path=destination
    )
    assert destination.read_text() != "old"
    assert list(tmp_path.glob(f".{destination.name}.*.tmp")) == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("sequence", 8),
        ("lineage_sha256", _sha("1")),
        ("binding_receipt_payload_sha256", _sha("2")),
        ("binding_receipt_payload_size_bytes", 104),
        ("receipt_identity_binding_sha256", _sha("3")),
    ],
)
def test_p81_stored_identity_binds_each_retained_p80_field(tmp_path, field: str, value) -> None:
    baseline = store_recovery_startup_stored_receipt_binding_receipt_replay_identity(
        _valid_p80(), destination_path=tmp_path / "baseline.json"
    )
    changed = store_recovery_startup_stored_receipt_binding_receipt_replay_identity(
        replace(_valid_p80(), **{field: value}),
        destination_path=tmp_path / "changed.json",
    )

    assert changed.stored_payload_sha256 != baseline.stored_payload_sha256


@pytest.mark.parametrize(
    "flag",
    [
        "expected_payload_identity_verified",
        "canonical_receipt_verified",
        "dependency_state_verified",
        "receipt_identity_binding_recomputed_verified",
    ],
)
def test_p81_rejects_weakened_p80_verification_flags(tmp_path, flag: str) -> None:
    with pytest.raises(ValueError, match="verification flags are incomplete"):
        store_recovery_startup_stored_receipt_binding_receipt_replay_identity(
            replace(_valid_p80(), **{flag: False}),
            destination_path=tmp_path / "p80.json",
        )


def test_p81_rejects_incompatible_state(tmp_path) -> None:
    with pytest.raises(ValueError, match="state is incompatible"):
        store_recovery_startup_stored_receipt_binding_receipt_replay_identity(
            replace(_valid_p80(), evidence_state="OTHER"),
            destination_path=tmp_path / "p80.json",
        )


def test_p81_rejects_automatic_control_escalation(tmp_path) -> None:
    with pytest.raises(ValueError, match="must not grant automatic-control authority"):
        store_recovery_startup_stored_receipt_binding_receipt_replay_identity(
            replace(_valid_p80(), automatic_control_allowed=True),
            destination_path=tmp_path / "p80.json",
        )


@pytest.mark.parametrize("sequence", [0, -1, True])
def test_p81_rejects_invalid_sequence(tmp_path, sequence) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        store_recovery_startup_stored_receipt_binding_receipt_replay_identity(
            replace(_valid_p80(), sequence=sequence),
            destination_path=tmp_path / "p80.json",
        )


def test_p81_rejects_malformed_hash_and_size(tmp_path) -> None:
    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        store_recovery_startup_stored_receipt_binding_receipt_replay_identity(
            replace(_valid_p80(), binding_receipt_payload_sha256="BAD"),
            destination_path=tmp_path / "p80.json",
        )
    with pytest.raises(ValueError, match="positive integer"):
        store_recovery_startup_stored_receipt_binding_receipt_replay_identity(
            replace(_valid_p80(), binding_receipt_payload_size_bytes=0),
            destination_path=tmp_path / "p80.json",
        )


def test_p81_rejects_non_p80_object(tmp_path) -> None:
    with pytest.raises(ValueError, match="incompatible type"):
        store_recovery_startup_stored_receipt_binding_receipt_replay_identity(
            object(), destination_path=tmp_path / "p80.json"
        )


def test_p81_truth_boundary_remains_local_historical_evidence() -> None:
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
