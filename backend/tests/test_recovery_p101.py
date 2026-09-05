from dataclasses import replace
import hashlib
import json

import pytest

from app.recovery_p100 import (
    EVIDENCE_STATE as P100_EVIDENCE_STATE,
    P98_EVIDENCE_STATE,
    RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingReceiptReplayEvidence,
)
from app.recovery_p101 import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    _FIELDS,
    store_recovery_startup_replayed_receipt_retained_identity_binding_receipt_replay_identity,
)


def _sha(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _evidence() -> RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingReceiptReplayEvidence:
    values: dict[str, object] = {}
    size = 201
    sha_index = 0
    for field, kind in _FIELDS:
        if kind == "sha":
            sha_index += 1
            values[field] = _sha(f"p101-{sha_index}")
        else:
            values[field] = 23 if field == "sequence" else size
            size += 1
    return RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingReceiptReplayEvidence(
        **values,
        expected_payload_identity_verified=True,
        canonical_receipt_verified=True,
        dependency_state_verified=True,
        replayed_receipt_retained_identity_binding_recomputed_verified=True,
        p98_evidence_state=P98_EVIDENCE_STATE,
    )


def test_p101_persists_strict_canonical_identity_and_exact_readback(tmp_path):
    destination = tmp_path / "nested" / "p100.identity.json"
    evidence = _evidence()
    result = store_recovery_startup_replayed_receipt_retained_identity_binding_receipt_replay_identity(
        evidence, destination_path=destination
    )
    raw = destination.read_bytes()
    decoded = json.loads(raw)
    assert raw == json.dumps(decoded, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    assert result.stored_payload_sha256 == hashlib.sha256(raw).hexdigest()
    assert result.stored_payload_size_bytes == len(raw)
    assert result.destination_path == str(destination)
    assert result.p100_evidence_state_verified is True
    assert result.p100_verification_flags_verified is True
    assert result.exact_readback_verified is True
    assert decoded["p100_evidence_state"] == P100_EVIDENCE_STATE
    for field, _ in _FIELDS:
        assert decoded[field] == getattr(evidence, field)


def test_p101_is_deterministic_and_replaces_without_temp_residue(tmp_path):
    destination = tmp_path / "p100.identity.json"
    first = store_recovery_startup_replayed_receipt_retained_identity_binding_receipt_replay_identity(
        _evidence(), destination_path=destination
    )
    before = destination.read_bytes()
    second = store_recovery_startup_replayed_receipt_retained_identity_binding_receipt_replay_identity(
        _evidence(), destination_path=destination
    )
    assert destination.read_bytes() == before
    assert first.stored_payload_sha256 == second.stored_payload_sha256
    assert first.stored_payload_size_bytes == second.stored_payload_size_bytes
    assert list(tmp_path.glob(".p100.identity.json.*.tmp")) == []


@pytest.mark.parametrize("flag", [
    "expected_payload_identity_verified",
    "canonical_receipt_verified",
    "dependency_state_verified",
    "replayed_receipt_retained_identity_binding_recomputed_verified",
])
def test_p101_rejects_weakened_p100_verification_flags(tmp_path, flag):
    with pytest.raises(ValueError, match="verification flags"):
        store_recovery_startup_replayed_receipt_retained_identity_binding_receipt_replay_identity(
            replace(_evidence(), **{flag: False}), destination_path=tmp_path / "identity.json"
        )


def test_p101_rejects_state_drift_and_automatic_control_escalation(tmp_path):
    with pytest.raises(ValueError, match="state is incompatible"):
        store_recovery_startup_replayed_receipt_retained_identity_binding_receipt_replay_identity(
            replace(_evidence(), evidence_state="DRIFT"), destination_path=tmp_path / "state.json"
        )
    with pytest.raises(ValueError, match="automatic-control"):
        store_recovery_startup_replayed_receipt_retained_identity_binding_receipt_replay_identity(
            replace(_evidence(), automatic_control_allowed=True), destination_path=tmp_path / "control.json"
        )


@pytest.mark.parametrize("bad", [True, 0, -1])
def test_p101_rejects_invalid_positive_integer_identity(tmp_path, bad):
    with pytest.raises(ValueError, match="positive integer"):
        store_recovery_startup_replayed_receipt_retained_identity_binding_receipt_replay_identity(
            replace(_evidence(), sequence=bad), destination_path=tmp_path / "identity.json"
        )


@pytest.mark.parametrize("bad", ["A" * 64, "g" * 64, "0" * 63])
def test_p101_rejects_malformed_sha_identity(tmp_path, bad):
    with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
        store_recovery_startup_replayed_receipt_retained_identity_binding_receipt_replay_identity(
            replace(_evidence(), lineage_sha256=bad), destination_path=tmp_path / "identity.json"
        )


@pytest.mark.parametrize("field,kind", _FIELDS)
def test_p101_payload_identity_is_sensitive_to_every_retained_field(tmp_path, field, kind):
    baseline = _evidence()
    first = store_recovery_startup_replayed_receipt_retained_identity_binding_receipt_replay_identity(
        baseline, destination_path=tmp_path / "a.json"
    )
    changed = 9999 if kind == "int" else _sha(f"changed-{field}")
    second = store_recovery_startup_replayed_receipt_retained_identity_binding_receipt_replay_identity(
        replace(baseline, **{field: changed}), destination_path=tmp_path / "b.json"
    )
    assert first.stored_payload_sha256 != second.stored_payload_sha256


def test_p101_rejects_incompatible_input_type(tmp_path):
    with pytest.raises(ValueError, match="incompatible type"):
        store_recovery_startup_replayed_receipt_retained_identity_binding_receipt_replay_identity(
            object(), destination_path=tmp_path / "identity.json"
        )


def test_p101_truth_boundary_stays_historical_and_non_authoritative():
    assert EVIDENCE_STATE.endswith("VERIFIED_IDENTITY_STORED")
    assert "local historical evidence" in TRUTH_BOUNDARY.lower()
    assert "not an authenticated" in TRUTH_BOUNDARY.lower()
    assert "freshness" in TRUTH_BOUNDARY.lower()
    assert "startup" in TRUTH_BOUNDARY.lower()
    assert "benchmark evidence" in TRUTH_BOUNDARY.lower()
    assert "novelty evidence" in TRUTH_BOUNDARY.lower()
