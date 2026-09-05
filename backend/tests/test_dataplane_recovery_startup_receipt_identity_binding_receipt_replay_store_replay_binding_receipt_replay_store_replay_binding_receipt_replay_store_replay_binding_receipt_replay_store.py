from dataclasses import replace
import hashlib
import json

import pytest

from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay import (
    EVIDENCE_STATE as P95_EVIDENCE_STATE,
    P93_EVIDENCE_STATE,
    RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayEvidence,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    _FIELDS,
    store_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity,
)


def _sha(ch: str) -> str:
    return ch * 64


def _evidence() -> RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayEvidence:
    return RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayEvidence(
        sequence=11,
        lineage_sha256=_sha("1"),
        binding_receipt_payload_sha256=_sha("2"),
        binding_receipt_payload_size_bytes=101,
        receipt_identity_binding_sha256=_sha("3"),
        retained_identity_payload_sha256=_sha("4"),
        retained_identity_payload_size_bytes=102,
        replay_stored_identity_binding_sha256=_sha("5"),
        replay_binding_receipt_payload_sha256=_sha("6"),
        replay_binding_receipt_payload_size_bytes=103,
        retained_replay_identity_payload_sha256=_sha("7"),
        retained_replay_identity_payload_size_bytes=104,
        replay_retained_identity_binding_sha256=_sha("8"),
        replay_retained_identity_binding_receipt_payload_sha256=_sha("9"),
        replay_retained_identity_binding_receipt_payload_size_bytes=105,
        retained_replay_receipt_identity_payload_sha256=_sha("a"),
        retained_replay_receipt_identity_payload_size_bytes=106,
        replay_retained_receipt_identity_binding_sha256=_sha("b"),
        replay_retained_receipt_identity_binding_receipt_payload_sha256=_sha("c"),
        replay_retained_receipt_identity_binding_receipt_payload_size_bytes=107,
        expected_payload_identity_verified=True,
        canonical_receipt_verified=True,
        dependency_state_verified=True,
        replay_retained_receipt_identity_binding_recomputed_verified=True,
        p93_evidence_state=P93_EVIDENCE_STATE,
    )


def test_p96_persists_strict_canonical_identity_and_exact_readback(tmp_path):
    destination = tmp_path / "nested" / "p95.identity.json"
    evidence = _evidence()

    result = store_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity(
        evidence, destination_path=destination
    )

    raw = destination.read_bytes()
    decoded = json.loads(raw)
    assert raw == json.dumps(decoded, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    assert result.stored_payload_sha256 == hashlib.sha256(raw).hexdigest()
    assert result.stored_payload_size_bytes == len(raw)
    assert result.destination_path == str(destination)
    assert result.p95_evidence_state_verified is True
    assert result.p95_verification_flags_verified is True
    assert result.exact_readback_verified is True
    assert decoded["p95_evidence_state"] == P95_EVIDENCE_STATE
    for field, _ in _FIELDS:
        assert decoded[field] == getattr(evidence, field)


def test_p96_is_deterministic_and_replaces_without_temp_residue(tmp_path):
    destination = tmp_path / "p95.identity.json"
    first = store_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity(
        _evidence(), destination_path=destination
    )
    before = destination.read_bytes()

    second = store_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity(
        _evidence(), destination_path=destination
    )

    assert destination.read_bytes() == before
    assert first.stored_payload_sha256 == second.stored_payload_sha256
    assert first.stored_payload_size_bytes == second.stored_payload_size_bytes
    assert list(tmp_path.glob(".p95.identity.json.*.tmp")) == []


@pytest.mark.parametrize(
    "flag",
    [
        "expected_payload_identity_verified",
        "canonical_receipt_verified",
        "dependency_state_verified",
        "replay_retained_receipt_identity_binding_recomputed_verified",
    ],
)
def test_p96_rejects_weakened_p95_verification_flags(tmp_path, flag):
    with pytest.raises(ValueError, match="verification flags"):
        store_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity(
            replace(_evidence(), **{flag: False}),
            destination_path=tmp_path / "identity.json",
        )


def test_p96_rejects_state_drift_and_automatic_control_escalation(tmp_path):
    with pytest.raises(ValueError, match="state is incompatible"):
        store_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity(
            replace(_evidence(), evidence_state="DRIFT"),
            destination_path=tmp_path / "state.json",
        )
    with pytest.raises(ValueError, match="automatic-control"):
        store_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity(
            replace(_evidence(), automatic_control_allowed=True),
            destination_path=tmp_path / "control.json",
        )


@pytest.mark.parametrize("bad", [True, 0, -1])
def test_p96_rejects_invalid_positive_integer_identity(tmp_path, bad):
    with pytest.raises(ValueError, match="positive integer"):
        store_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity(
            replace(_evidence(), sequence=bad),
            destination_path=tmp_path / "identity.json",
        )


@pytest.mark.parametrize("bad", ["A" * 64, "0" * 63, "g" * 64])
def test_p96_rejects_malformed_sha256_identity(tmp_path, bad):
    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        store_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity(
            replace(_evidence(), lineage_sha256=bad),
            destination_path=tmp_path / "identity.json",
        )


@pytest.mark.parametrize("field,kind", _FIELDS)
def test_p96_stored_identity_is_sensitive_to_every_retained_semantic_field(tmp_path, field, kind):
    base = _evidence()
    base_result = store_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity(
        base, destination_path=tmp_path / "base.json"
    )
    current = getattr(base, field)
    changed = current + 1 if kind == "int" else ("d" * 64 if current != "d" * 64 else "e" * 64)
    changed_result = store_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity(
        replace(base, **{field: changed}), destination_path=tmp_path / "changed.json"
    )
    assert changed_result.stored_payload_sha256 != base_result.stored_payload_sha256


def test_p96_rejects_incompatible_evidence_type(tmp_path):
    with pytest.raises(ValueError, match="incompatible type"):
        store_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity(
            object(), destination_path=tmp_path / "identity.json"
        )


def test_p96_truth_boundary_is_explicit_and_non_authoritative(tmp_path):
    result = store_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity(
        _evidence(), destination_path=tmp_path / "identity.json"
    )

    assert result.evidence_state == EVIDENCE_STATE
    assert result.automatic_control_allowed is False
    assert "local historical evidence" in TRUTH_BOUNDARY
    assert "not an authenticated" in TRUTH_BOUNDARY
    assert "freshness/latest/global/monotonic" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark evidence" in TRUTH_BOUNDARY
    assert "novelty evidence" in TRUTH_BOUNDARY
    assert "automatic-control authority" in TRUTH_BOUNDARY
