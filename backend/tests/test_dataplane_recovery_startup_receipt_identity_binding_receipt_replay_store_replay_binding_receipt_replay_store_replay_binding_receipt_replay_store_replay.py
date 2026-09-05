from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay import (
    EVIDENCE_STATE as P90_EVIDENCE_STATE,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store import (
    EVIDENCE_STATE as P91_EVIDENCE_STATE,
    RecoveryStartupReplayRetainedIdentityBindingReceiptReplayIdentityStoreEvidence,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    verify_recovery_startup_replay_retained_identity_binding_receipt_replay_identity_store,
)

H = {
    "lineage": "1" * 64,
    "binding_receipt": "2" * 64,
    "receipt_binding": "3" * 64,
    "retained": "4" * 64,
    "replay_stored": "5" * 64,
    "replay_receipt": "6" * 64,
    "retained_replay": "7" * 64,
    "replay_retained": "8" * 64,
    "p89_receipt": "9" * 64,
}


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "binding_receipt_payload_sha256": H["binding_receipt"],
        "binding_receipt_payload_size_bytes": 101,
        "lineage_sha256": H["lineage"],
        "p90_evidence_state": P90_EVIDENCE_STATE,
        "receipt_identity_binding_sha256": H["receipt_binding"],
        "replay_binding_receipt_payload_sha256": H["replay_receipt"],
        "replay_binding_receipt_payload_size_bytes": 202,
        "replay_retained_identity_binding_receipt_payload_sha256": H["p89_receipt"],
        "replay_retained_identity_binding_receipt_payload_size_bytes": 505,
        "replay_retained_identity_binding_sha256": H["replay_retained"],
        "replay_stored_identity_binding_sha256": H["replay_stored"],
        "retained_identity_payload_sha256": H["retained"],
        "retained_identity_payload_size_bytes": 303,
        "retained_replay_identity_payload_sha256": H["retained_replay"],
        "retained_replay_identity_payload_size_bytes": 404,
        "sequence": 23,
    }
    payload.update(overrides)
    return payload


def _canonical(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _evidence(path, raw: bytes | None = None, **overrides: object):
    stored = _canonical(_payload()) if raw is None else raw
    path.write_bytes(stored)
    kwargs = dict(
        sequence=23,
        lineage_sha256=H["lineage"],
        binding_receipt_payload_sha256=H["binding_receipt"],
        binding_receipt_payload_size_bytes=101,
        receipt_identity_binding_sha256=H["receipt_binding"],
        retained_identity_payload_sha256=H["retained"],
        retained_identity_payload_size_bytes=303,
        replay_stored_identity_binding_sha256=H["replay_stored"],
        replay_binding_receipt_payload_sha256=H["replay_receipt"],
        replay_binding_receipt_payload_size_bytes=202,
        retained_replay_identity_payload_sha256=H["retained_replay"],
        retained_replay_identity_payload_size_bytes=404,
        replay_retained_identity_binding_sha256=H["replay_retained"],
        replay_retained_identity_binding_receipt_payload_sha256=H["p89_receipt"],
        replay_retained_identity_binding_receipt_payload_size_bytes=505,
        stored_payload_sha256=hashlib.sha256(stored).hexdigest(),
        stored_payload_size_bytes=len(stored),
        destination_path=str(path),
        p90_evidence_state_verified=True,
        p90_verification_flags_verified=True,
        exact_readback_verified=True,
    )
    kwargs.update(overrides)
    return RecoveryStartupReplayRetainedIdentityBindingReceiptReplayIdentityStoreEvidence(**kwargs)


def test_p92_replays_exact_canonical_p91_record(tmp_path):
    evidence = _evidence(tmp_path / "p91.json")
    result = verify_recovery_startup_replay_retained_identity_binding_receipt_replay_identity_store(evidence)
    assert result.evidence_state == EVIDENCE_STATE
    assert result.automatic_control_allowed is False
    assert result.sequence == evidence.sequence
    assert result.stored_payload_sha256 == evidence.stored_payload_sha256
    assert result.stored_payload_size_bytes == evidence.stored_payload_size_bytes
    assert result.p91_evidence_state_verified is True
    assert result.p91_verification_flags_verified is True
    assert result.exact_payload_identity_verified is True
    assert result.canonical_record_verified is True
    assert result.semantic_agreement_verified is True


def test_p92_export_preserves_verified_read_only_boundary(tmp_path):
    evidence = _evidence(tmp_path / "p91.json")
    exported = verify_recovery_startup_replay_retained_identity_binding_receipt_replay_identity_store(evidence).as_dict()
    assert exported["evidence_state"] == EVIDENCE_STATE
    assert exported["automatic_control_allowed"] is False
    assert exported["p91_evidence_state_verified"] is True
    assert exported["p91_verification_flags_verified"] is True
    assert exported["exact_payload_identity_verified"] is True
    assert exported["canonical_record_verified"] is True
    assert exported["semantic_agreement_verified"] is True
    assert exported["truth_boundary"] == TRUTH_BOUNDARY


def test_p92_can_replay_explicit_source_path(tmp_path):
    original = tmp_path / "original.json"
    alternate = tmp_path / "alternate.json"
    evidence = _evidence(original)
    alternate.write_bytes(original.read_bytes())
    result = verify_recovery_startup_replay_retained_identity_binding_receipt_replay_identity_store(
        evidence, source_path=alternate
    )
    assert result.source_path == str(alternate)


@pytest.mark.parametrize("flag", ["p90_evidence_state_verified", "p90_verification_flags_verified", "exact_readback_verified"])
def test_p92_rejects_weakened_p91_flags(tmp_path, flag):
    evidence = _evidence(tmp_path / "p91.json")
    with pytest.raises(ValueError, match="verification flags"):
        verify_recovery_startup_replay_retained_identity_binding_receipt_replay_identity_store(
            replace(evidence, **{flag: False})
        )


def test_p92_rejects_wrong_p91_state_and_control_escalation(tmp_path):
    evidence = _evidence(tmp_path / "p91.json")
    with pytest.raises(ValueError, match="state is incompatible"):
        verify_recovery_startup_replay_retained_identity_binding_receipt_replay_identity_store(
            replace(evidence, evidence_state="wrong")
        )
    with pytest.raises(ValueError, match="automatic-control"):
        verify_recovery_startup_replay_retained_identity_binding_receipt_replay_identity_store(
            replace(evidence, automatic_control_allowed=True)
        )


@pytest.mark.parametrize("value", [True, 0, -1])
def test_p92_rejects_invalid_sequence(tmp_path, value):
    evidence = _evidence(tmp_path / "p91.json")
    with pytest.raises(ValueError, match="positive integer"):
        verify_recovery_startup_replay_retained_identity_binding_receipt_replay_identity_store(
            replace(evidence, sequence=value)
        )


@pytest.mark.parametrize("field", [
    "lineage_sha256",
    "binding_receipt_payload_sha256",
    "receipt_identity_binding_sha256",
    "retained_identity_payload_sha256",
    "replay_stored_identity_binding_sha256",
    "replay_binding_receipt_payload_sha256",
    "retained_replay_identity_payload_sha256",
    "replay_retained_identity_binding_sha256",
    "replay_retained_identity_binding_receipt_payload_sha256",
    "stored_payload_sha256",
])
def test_p92_rejects_malformed_hashes(tmp_path, field):
    evidence = _evidence(tmp_path / "p91.json")
    with pytest.raises(ValueError, match="64 lowercase"):
        verify_recovery_startup_replay_retained_identity_binding_receipt_replay_identity_store(
            replace(evidence, **{field: "ABC"})
        )


@pytest.mark.parametrize("field", [
    "binding_receipt_payload_size_bytes",
    "retained_identity_payload_size_bytes",
    "replay_binding_receipt_payload_size_bytes",
    "retained_replay_identity_payload_size_bytes",
    "replay_retained_identity_binding_receipt_payload_size_bytes",
    "stored_payload_size_bytes",
])
def test_p92_rejects_invalid_sizes(tmp_path, field):
    evidence = _evidence(tmp_path / "p91.json")
    with pytest.raises(ValueError, match="positive integer"):
        verify_recovery_startup_replay_retained_identity_binding_receipt_replay_identity_store(
            replace(evidence, **{field: 0})
        )


def test_p92_rejects_byte_and_size_drift(tmp_path):
    path = tmp_path / "p91.json"
    evidence = _evidence(path)
    raw = path.read_bytes()
    path.write_bytes(raw[:-1] + (b"0" if raw[-1:] != b"0" else b"1"))
    with pytest.raises(ValueError, match="SHA-256"):
        verify_recovery_startup_replay_retained_identity_binding_receipt_replay_identity_store(evidence)
    path.write_bytes(raw + b"x")
    with pytest.raises(ValueError, match="byte length"):
        verify_recovery_startup_replay_retained_identity_binding_receipt_replay_identity_store(evidence)


def test_p92_rejects_noncanonical_json_even_with_matching_identity(tmp_path):
    path = tmp_path / "p91.json"
    raw = json.dumps(_payload(), sort_keys=False, indent=2).encode()
    evidence = _evidence(path, raw=raw)
    with pytest.raises(ValueError, match="strict canonical"):
        verify_recovery_startup_replay_retained_identity_binding_receipt_replay_identity_store(evidence)


def test_p92_rejects_schema_drift_even_with_matching_identity(tmp_path):
    path = tmp_path / "p91.json"
    raw = _canonical(_payload(extra="field"))
    evidence = _evidence(path, raw=raw)
    with pytest.raises(ValueError, match="schema"):
        verify_recovery_startup_replay_retained_identity_binding_receipt_replay_identity_store(evidence)


def test_p92_rejects_embedded_p90_state_drift_even_with_matching_identity(tmp_path):
    path = tmp_path / "p91.json"
    raw = _canonical(_payload(p90_evidence_state="forged"))
    evidence = _evidence(path, raw=raw)
    with pytest.raises(ValueError, match="P90 evidence state"):
        verify_recovery_startup_replay_retained_identity_binding_receipt_replay_identity_store(evidence)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sequence", 24),
        ("lineage_sha256", "a" * 64),
        ("binding_receipt_payload_sha256", "b" * 64),
        ("binding_receipt_payload_size_bytes", 102),
        ("receipt_identity_binding_sha256", "c" * 64),
        ("retained_identity_payload_sha256", "d" * 64),
        ("retained_identity_payload_size_bytes", 304),
        ("replay_stored_identity_binding_sha256", "e" * 64),
        ("replay_binding_receipt_payload_sha256", "f" * 64),
        ("replay_binding_receipt_payload_size_bytes", 203),
        ("retained_replay_identity_payload_sha256", "0" * 64),
        ("retained_replay_identity_payload_size_bytes", 405),
        ("replay_retained_identity_binding_sha256", "a" * 64),
        ("replay_retained_identity_binding_receipt_payload_sha256", "b" * 64),
        ("replay_retained_identity_binding_receipt_payload_size_bytes", 506),
    ],
)
def test_p92_rejects_semantic_forgery_with_recomputed_file_identity(tmp_path, field, value):
    path = tmp_path / "p91.json"
    raw = _canonical(_payload(**{field: value}))
    evidence = _evidence(path, raw=raw)
    with pytest.raises(ValueError, match="semantics differ"):
        verify_recovery_startup_replay_retained_identity_binding_receipt_replay_identity_store(evidence)


def test_p92_rejects_non_p91_input():
    with pytest.raises(ValueError, match="incompatible type"):
        verify_recovery_startup_replay_retained_identity_binding_receipt_replay_identity_store(object())


def test_p92_truth_boundary_is_explicitly_historical_read_only_and_non_authoritative():
    lowered = TRUTH_BOUNDARY.lower()
    for phrase in (
        "historical read-only",
        "does not authenticate",
        "freshness",
        "rollback",
        "coordinated replacement",
        "atomic snapshot after return",
        "authorize startup or mutation",
        "production readiness",
        "benchmark evidence",
        "novelty evidence",
        "automatic-control authority",
    ):
        assert phrase in lowered
    assert P91_EVIDENCE_STATE != EVIDENCE_STATE
