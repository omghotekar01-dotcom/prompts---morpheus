from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay import (
    EVIDENCE_STATE as P95_EVIDENCE_STATE,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store import (
    EVIDENCE_STATE as P96_EVIDENCE_STATE,
    RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoreEvidence,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    verify_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity_store,
)

SHA_FIELDS = (
    "lineage_sha256",
    "binding_receipt_payload_sha256",
    "receipt_identity_binding_sha256",
    "retained_identity_payload_sha256",
    "replay_stored_identity_binding_sha256",
    "replay_binding_receipt_payload_sha256",
    "retained_replay_identity_payload_sha256",
    "replay_retained_identity_binding_sha256",
    "replay_retained_identity_binding_receipt_payload_sha256",
    "retained_replay_receipt_identity_payload_sha256",
    "replay_retained_receipt_identity_binding_sha256",
    "replay_retained_receipt_identity_binding_receipt_payload_sha256",
)
INT_FIELDS = (
    "sequence",
    "binding_receipt_payload_size_bytes",
    "retained_identity_payload_size_bytes",
    "replay_binding_receipt_payload_size_bytes",
    "retained_replay_identity_payload_size_bytes",
    "replay_retained_identity_binding_receipt_payload_size_bytes",
    "retained_replay_receipt_identity_payload_size_bytes",
    "replay_retained_receipt_identity_binding_receipt_payload_size_bytes",
)
ALL_FIELDS = (
    "sequence",
    "lineage_sha256",
    "binding_receipt_payload_sha256",
    "binding_receipt_payload_size_bytes",
    "receipt_identity_binding_sha256",
    "retained_identity_payload_sha256",
    "retained_identity_payload_size_bytes",
    "replay_stored_identity_binding_sha256",
    "replay_binding_receipt_payload_sha256",
    "replay_binding_receipt_payload_size_bytes",
    "retained_replay_identity_payload_sha256",
    "retained_replay_identity_payload_size_bytes",
    "replay_retained_identity_binding_sha256",
    "replay_retained_identity_binding_receipt_payload_sha256",
    "replay_retained_identity_binding_receipt_payload_size_bytes",
    "retained_replay_receipt_identity_payload_sha256",
    "retained_replay_receipt_identity_payload_size_bytes",
    "replay_retained_receipt_identity_binding_sha256",
    "replay_retained_receipt_identity_binding_receipt_payload_sha256",
    "replay_retained_receipt_identity_binding_receipt_payload_size_bytes",
)


def _canonical(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _fixture(tmp_path):
    values = {"sequence": 7}
    for index, field in enumerate(SHA_FIELDS, start=1):
        values[field] = hashlib.sha256(f"field-{index}".encode()).hexdigest()
    for index, field in enumerate(INT_FIELDS[1:], start=101):
        values[field] = index
    payload = {field: values[field] for field in ALL_FIELDS}
    payload["p95_evidence_state"] = P95_EVIDENCE_STATE
    encoded = _canonical(payload)
    path = tmp_path / "p96.json"
    path.write_bytes(encoded)
    evidence = RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoreEvidence(
        **values,
        stored_payload_sha256=hashlib.sha256(encoded).hexdigest(),
        stored_payload_size_bytes=len(encoded),
        destination_path=str(path),
        p95_evidence_state_verified=True,
        p95_verification_flags_verified=True,
        exact_readback_verified=True,
    )
    return evidence, path, payload


def test_p97_verifies_canonical_p96_record(tmp_path):
    evidence, path, _ = _fixture(tmp_path)
    result = verify_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity_store(evidence)
    assert result.source_path == str(path)
    assert result.evidence_state == EVIDENCE_STATE
    assert result.automatic_control_allowed is False
    assert result.p96_evidence_state_verified is True
    assert result.p96_verification_flags_verified is True
    assert result.exact_payload_identity_verified is True
    assert result.canonical_record_verified is True
    assert result.semantic_agreement_verified is True


def test_p97_supports_explicit_alternate_source_path(tmp_path):
    evidence, _, payload = _fixture(tmp_path)
    alternate = tmp_path / "copy.json"
    alternate.write_bytes(_canonical(payload))
    result = verify_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity_store(
        evidence, source_path=alternate
    )
    assert result.source_path == str(alternate)


@pytest.mark.parametrize("flag", ["p95_evidence_state_verified", "p95_verification_flags_verified", "exact_readback_verified"])
def test_p97_rejects_weakened_p96_verification_contract(tmp_path, flag):
    evidence, _, _ = _fixture(tmp_path)
    with pytest.raises(ValueError, match="verification flags"):
        verify_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity_store(
            replace(evidence, **{flag: False})
        )


def test_p97_rejects_p96_state_drift_and_control_escalation(tmp_path):
    evidence, _, _ = _fixture(tmp_path)
    with pytest.raises(ValueError, match="state is incompatible"):
        verify_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity_store(
            replace(evidence, evidence_state="drift")
        )
    with pytest.raises(ValueError, match="automatic-control"):
        verify_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity_store(
            replace(evidence, automatic_control_allowed=True)
        )


@pytest.mark.parametrize("bad", [0, -1, True])
def test_p97_rejects_invalid_positive_integer_identity(tmp_path, bad):
    evidence, _, _ = _fixture(tmp_path)
    with pytest.raises(ValueError, match="positive integer"):
        verify_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity_store(
            replace(evidence, sequence=bad)
        )


def test_p97_rejects_malformed_hash_identity(tmp_path):
    evidence, _, _ = _fixture(tmp_path)
    with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
        verify_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity_store(
            replace(evidence, lineage_sha256="A" * 64)
        )


def test_p97_rejects_same_size_byte_tamper_and_size_drift(tmp_path):
    evidence, path, _ = _fixture(tmp_path)
    raw = path.read_bytes()
    path.write_bytes(raw[:-1] + (b"X" if raw[-1:] != b"X" else b"Y"))
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity_store(evidence)
    path.write_bytes(raw + b" ")
    with pytest.raises(ValueError, match="byte length mismatch"):
        verify_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity_store(evidence)


def test_p97_rejects_noncanonical_json_with_recomputed_outer_identity(tmp_path):
    evidence, path, payload = _fixture(tmp_path)
    encoded = json.dumps(payload, indent=2, sort_keys=True).encode()
    path.write_bytes(encoded)
    evidence = replace(
        evidence,
        stored_payload_sha256=hashlib.sha256(encoded).hexdigest(),
        stored_payload_size_bytes=len(encoded),
    )
    with pytest.raises(ValueError, match="strict canonical JSON"):
        verify_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity_store(evidence)


def test_p97_rejects_schema_and_embedded_state_drift(tmp_path):
    evidence, path, payload = _fixture(tmp_path)
    payload["extra"] = "drift"
    encoded = _canonical(payload)
    path.write_bytes(encoded)
    with pytest.raises(ValueError, match="schema is incompatible"):
        verify_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity_store(
            replace(evidence, stored_payload_sha256=hashlib.sha256(encoded).hexdigest(), stored_payload_size_bytes=len(encoded))
        )
    payload.pop("extra")
    payload["p95_evidence_state"] = "drift"
    encoded = _canonical(payload)
    path.write_bytes(encoded)
    with pytest.raises(ValueError, match="P95 evidence state"):
        verify_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity_store(
            replace(evidence, stored_payload_sha256=hashlib.sha256(encoded).hexdigest(), stored_payload_size_bytes=len(encoded))
        )


@pytest.mark.parametrize("field", ALL_FIELDS)
def test_p97_rejects_semantic_forgery_even_with_recomputed_outer_identity(tmp_path, field):
    evidence, path, payload = _fixture(tmp_path)
    if field in SHA_FIELDS:
        payload[field] = hashlib.sha256((field + "-forged").encode()).hexdigest()
    else:
        payload[field] = int(payload[field]) + 1
    encoded = _canonical(payload)
    path.write_bytes(encoded)
    forged_outer = replace(
        evidence,
        stored_payload_sha256=hashlib.sha256(encoded).hexdigest(),
        stored_payload_size_bytes=len(encoded),
    )
    with pytest.raises(ValueError, match=f"disagrees on {field}"):
        verify_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity_store(forged_outer)


def test_p97_rejects_incompatible_input_type():
    with pytest.raises(ValueError, match="incompatible type"):
        verify_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity_store(object())


def test_p97_truth_boundary_is_explicit_and_non_authoritative(tmp_path):
    evidence, _, _ = _fixture(tmp_path)
    result = verify_recovery_startup_replay_retained_receipt_identity_binding_receipt_replay_identity_store(evidence)
    rendered = result.as_dict()
    assert rendered["truth_boundary"] == TRUTH_BOUNDARY
    assert "historical read-only" in TRUTH_BOUNDARY
    assert "does not authenticate" in TRUTH_BOUNDARY
    assert "freshness/latest/global/monotonic" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark evidence" in TRUTH_BOUNDARY
    assert "novelty evidence" in TRUTH_BOUNDARY
    assert rendered["automatic_control_allowed"] is False
