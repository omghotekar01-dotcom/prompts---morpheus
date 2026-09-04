from dataclasses import replace
import json

import pytest

from app.dataplane_recovery_startup_receipt_identity_binding import EVIDENCE_STATE as P78_EVIDENCE_STATE
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay import (
    EVIDENCE_STATE as P80_EVIDENCE_STATE,
    RecoveryStartupStoredReceiptBindingReceiptReplayEvidence,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store import (
    EVIDENCE_STATE as P81_EVIDENCE_STATE,
    RecoveryStartupStoredReceiptBindingReceiptReplayIdentityStoreEvidence,
    store_recovery_startup_stored_receipt_binding_receipt_replay_identity,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay import (
    EVIDENCE_STATE as P82_EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    replay_recovery_startup_stored_receipt_binding_receipt_replay_identity,
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


def _stored(tmp_path):
    destination = tmp_path / "p80-replay.json"
    evidence = store_recovery_startup_stored_receipt_binding_receipt_replay_identity(
        _valid_p80(), destination_path=destination
    )
    return evidence, destination


def test_p82_replays_exact_p81_record(tmp_path) -> None:
    stored, destination = _stored(tmp_path)
    replay = replay_recovery_startup_stored_receipt_binding_receipt_replay_identity(stored)

    assert replay.sequence == stored.sequence
    assert replay.lineage_sha256 == stored.lineage_sha256
    assert replay.binding_receipt_payload_sha256 == stored.binding_receipt_payload_sha256
    assert replay.binding_receipt_payload_size_bytes == stored.binding_receipt_payload_size_bytes
    assert replay.receipt_identity_binding_sha256 == stored.receipt_identity_binding_sha256
    assert replay.stored_payload_sha256 == stored.stored_payload_sha256
    assert replay.stored_payload_size_bytes == stored.stored_payload_size_bytes
    assert replay.source_path == str(destination)
    assert replay.expected_payload_identity_verified is True
    assert replay.canonical_record_verified is True
    assert replay.p80_evidence_state_verified is True
    assert replay.semantic_identity_verified is True
    assert replay.evidence_state == P82_EVIDENCE_STATE
    assert replay.automatic_control_allowed is False


def test_p82_accepts_explicit_matching_source_path(tmp_path) -> None:
    stored, destination = _stored(tmp_path)
    replay = replay_recovery_startup_stored_receipt_binding_receipt_replay_identity(
        stored, source_path=destination
    )
    assert replay.source_path == str(destination)


@pytest.mark.parametrize(
    "field",
    ["p80_evidence_state_verified", "p80_verification_flags_verified", "exact_readback_verified"],
)
def test_p82_rejects_weakened_p81_verification(tmp_path, field: str) -> None:
    stored, _ = _stored(tmp_path)
    with pytest.raises(ValueError, match="incomplete"):
        replay_recovery_startup_stored_receipt_binding_receipt_replay_identity(
            replace(stored, **{field: False})
        )


def test_p82_rejects_incompatible_p81_state(tmp_path) -> None:
    stored, _ = _stored(tmp_path)
    with pytest.raises(ValueError, match="state is incompatible"):
        replay_recovery_startup_stored_receipt_binding_receipt_replay_identity(
            replace(stored, evidence_state="OTHER")
        )


def test_p82_rejects_automatic_control_escalation(tmp_path) -> None:
    stored, _ = _stored(tmp_path)
    with pytest.raises(ValueError, match="must not grant automatic-control authority"):
        replay_recovery_startup_stored_receipt_binding_receipt_replay_identity(
            replace(stored, automatic_control_allowed=True)
        )


@pytest.mark.parametrize("sequence", [0, -1, True])
def test_p82_rejects_invalid_sequence(tmp_path, sequence) -> None:
    stored, _ = _stored(tmp_path)
    with pytest.raises(ValueError, match="positive integer"):
        replay_recovery_startup_stored_receipt_binding_receipt_replay_identity(
            replace(stored, sequence=sequence)
        )


def test_p82_rejects_malformed_hash_and_size(tmp_path) -> None:
    stored, _ = _stored(tmp_path)
    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        replay_recovery_startup_stored_receipt_binding_receipt_replay_identity(
            replace(stored, binding_receipt_payload_sha256="BAD")
        )
    with pytest.raises(ValueError, match="positive integer"):
        replay_recovery_startup_stored_receipt_binding_receipt_replay_identity(
            replace(stored, binding_receipt_payload_size_bytes=0)
        )


def test_p82_rejects_post_p81_byte_drift(tmp_path) -> None:
    stored, destination = _stored(tmp_path)
    raw = bytearray(destination.read_bytes())
    raw[-1] = ord(" ")
    destination.write_bytes(raw)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        replay_recovery_startup_stored_receipt_binding_receipt_replay_identity(stored)


def test_p82_rejects_size_drift(tmp_path) -> None:
    stored, destination = _stored(tmp_path)
    destination.write_bytes(destination.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="byte length mismatch"):
        replay_recovery_startup_stored_receipt_binding_receipt_replay_identity(stored)


def test_p82_rejects_semantic_drift_even_with_matching_recomputed_store_identity(tmp_path) -> None:
    stored, destination = _stored(tmp_path)
    payload = json.loads(destination.read_text())
    payload["sequence"] = 8
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    destination.write_bytes(encoded)
    import hashlib
    forged = replace(
        stored,
        stored_payload_sha256=hashlib.sha256(encoded).hexdigest(),
        stored_payload_size_bytes=len(encoded),
    )
    with pytest.raises(ValueError, match="sequence mismatch"):
        replay_recovery_startup_stored_receipt_binding_receipt_replay_identity(forged)


def test_p82_rejects_p80_evidence_state_drift_inside_record(tmp_path) -> None:
    stored, destination = _stored(tmp_path)
    payload = json.loads(destination.read_text())
    payload["p80_evidence_state"] = "OTHER"
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    destination.write_bytes(encoded)
    import hashlib
    forged = replace(
        stored,
        stored_payload_sha256=hashlib.sha256(encoded).hexdigest(),
        stored_payload_size_bytes=len(encoded),
    )
    with pytest.raises(ValueError, match="P80 evidence state mismatch"):
        replay_recovery_startup_stored_receipt_binding_receipt_replay_identity(forged)


def test_p82_rejects_non_p81_object() -> None:
    with pytest.raises(ValueError, match="incompatible type"):
        replay_recovery_startup_stored_receipt_binding_receipt_replay_identity(object())


def test_p82_truth_boundary_remains_historical_read_only_evidence() -> None:
    boundary = TRUTH_BOUNDARY.lower()
    for phrase in (
        "read-only",
        "historical",
        "does not authenticate",
        "freshness",
        "rollback",
        "authorize startup",
        "production readiness",
        "benchmark evidence",
        "novelty evidence",
        "automatic-control authority",
    ):
        assert phrase in boundary
