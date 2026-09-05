from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.recovery_p100 import EVIDENCE_STATE as P100_EVIDENCE_STATE
from app.recovery_p101 import (
    EVIDENCE_STATE as P101_EVIDENCE_STATE,
    RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingReceiptReplayIdentityStoreEvidence,
)
from app.recovery_p102 import EVIDENCE_STATE, TRUTH_BOUNDARY, _FIELDS, verify_p101_retained_identity


def _sha(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _canonical(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _fixture(tmp_path):
    values: dict[str, object] = {}
    size = 301
    sha_index = 0
    for field, kind in _FIELDS:
        if kind == "sha":
            sha_index += 1
            values[field] = _sha(f"p102-{sha_index}")
        else:
            values[field] = 29 if field == "sequence" else size
            size += 1

    payload = {field: values[field] for field, _ in _FIELDS}
    payload["p100_evidence_state"] = P100_EVIDENCE_STATE
    encoded = _canonical(payload)
    path = tmp_path / "p101.json"
    path.write_bytes(encoded)
    evidence = RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingReceiptReplayIdentityStoreEvidence(
        **values,
        stored_payload_sha256=hashlib.sha256(encoded).hexdigest(),
        stored_payload_size_bytes=len(encoded),
        destination_path=str(path),
        p100_evidence_state_verified=True,
        p100_verification_flags_verified=True,
        exact_readback_verified=True,
    )
    return evidence, path, payload


def test_p102_verifies_canonical_p101_record(tmp_path):
    evidence, path, _ = _fixture(tmp_path)
    result = verify_p101_retained_identity(evidence)
    assert result.source_path == str(path)
    assert result.evidence_state == EVIDENCE_STATE
    assert result.automatic_control_allowed is False
    assert result.p101_evidence_state_verified is True
    assert result.p101_verification_flags_verified is True
    assert result.exact_payload_identity_verified is True
    assert result.canonical_record_verified is True
    assert result.semantic_agreement_verified is True
    for field, _ in _FIELDS:
        assert getattr(result, field) == getattr(evidence, field)


def test_p102_supports_explicit_alternate_source(tmp_path):
    evidence, _, payload = _fixture(tmp_path)
    alternate = tmp_path / "archive" / "p101.json"
    alternate.parent.mkdir()
    alternate.write_bytes(_canonical(payload))
    result = verify_p101_retained_identity(evidence, source_path=alternate)
    assert result.source_path == str(alternate)


@pytest.mark.parametrize(
    "flag",
    ["p100_evidence_state_verified", "p100_verification_flags_verified", "exact_readback_verified"],
)
def test_p102_rejects_weakened_p101_verification_flags(tmp_path, flag):
    evidence, _, _ = _fixture(tmp_path)
    with pytest.raises(ValueError, match="verification flags"):
        verify_p101_retained_identity(replace(evidence, **{flag: False}))


def test_p102_rejects_p101_state_drift_and_automatic_control_escalation(tmp_path):
    evidence, _, _ = _fixture(tmp_path)
    with pytest.raises(ValueError, match="state is incompatible"):
        verify_p101_retained_identity(replace(evidence, evidence_state="DRIFT"))
    with pytest.raises(ValueError, match="automatic-control"):
        verify_p101_retained_identity(replace(evidence, automatic_control_allowed=True))


@pytest.mark.parametrize("bad", [True, 0, -1])
def test_p102_rejects_invalid_positive_integer_identity(tmp_path, bad):
    evidence, _, _ = _fixture(tmp_path)
    with pytest.raises(ValueError, match="positive integer"):
        verify_p101_retained_identity(replace(evidence, sequence=bad))


@pytest.mark.parametrize("bad", ["A" * 64, "g" * 64, "0" * 63, 7])
def test_p102_rejects_malformed_sha256_identity(tmp_path, bad):
    evidence, _, _ = _fixture(tmp_path)
    with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
        verify_p101_retained_identity(replace(evidence, lineage_sha256=bad))


def test_p102_rejects_same_size_byte_tampering(tmp_path):
    evidence, path, _ = _fixture(tmp_path)
    raw = bytearray(path.read_bytes())
    raw[-2] = ord("0") if raw[-2] != ord("0") else ord("1")
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_p101_retained_identity(evidence)


def test_p102_rejects_size_drift(tmp_path):
    evidence, path, _ = _fixture(tmp_path)
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="byte length mismatch"):
        verify_p101_retained_identity(evidence)


def test_p102_rejects_noncanonical_json_even_with_recomputed_outer_identity(tmp_path):
    evidence, path, payload = _fixture(tmp_path)
    raw = json.dumps(payload, indent=2, sort_keys=False).encode()
    path.write_bytes(raw)
    forged = replace(
        evidence,
        stored_payload_sha256=hashlib.sha256(raw).hexdigest(),
        stored_payload_size_bytes=len(raw),
    )
    with pytest.raises(ValueError, match="strict canonical JSON"):
        verify_p101_retained_identity(forged)


def test_p102_rejects_schema_drift_with_recomputed_outer_identity(tmp_path):
    evidence, path, payload = _fixture(tmp_path)
    payload["unexpected"] = "field"
    raw = _canonical(payload)
    path.write_bytes(raw)
    forged = replace(
        evidence,
        stored_payload_sha256=hashlib.sha256(raw).hexdigest(),
        stored_payload_size_bytes=len(raw),
    )
    with pytest.raises(ValueError, match="schema is incompatible"):
        verify_p101_retained_identity(forged)


def test_p102_rejects_embedded_p100_state_drift_with_recomputed_outer_identity(tmp_path):
    evidence, path, payload = _fixture(tmp_path)
    payload["p100_evidence_state"] = "DRIFT"
    raw = _canonical(payload)
    path.write_bytes(raw)
    forged = replace(
        evidence,
        stored_payload_sha256=hashlib.sha256(raw).hexdigest(),
        stored_payload_size_bytes=len(raw),
    )
    with pytest.raises(ValueError, match="incompatible P100 evidence state"):
        verify_p101_retained_identity(forged)


@pytest.mark.parametrize("field,kind", _FIELDS)
def test_p102_rejects_semantic_forgery_even_with_recomputed_outer_identity(tmp_path, field, kind):
    evidence, path, payload = _fixture(tmp_path)
    payload[field] = (
        getattr(evidence, field) + 1
        if kind == "int"
        else _sha(f"forged-{field}")
    )
    raw = _canonical(payload)
    path.write_bytes(raw)
    forged = replace(
        evidence,
        stored_payload_sha256=hashlib.sha256(raw).hexdigest(),
        stored_payload_size_bytes=len(raw),
    )
    with pytest.raises(ValueError, match=f"disagrees on {field}"):
        verify_p101_retained_identity(forged)


@pytest.mark.parametrize(
    "mutator,match",
    [
        (lambda raw: b"\xff" + raw[1:], "not valid UTF-8"),
        (lambda raw: b"{" + raw[1:-1], "not valid JSON"),
        (lambda raw: _canonical([]), "must be a JSON object"),
    ],
)
def test_p102_rejects_incompatible_serialized_forms(tmp_path, mutator, match):
    evidence, path, _ = _fixture(tmp_path)
    raw = mutator(path.read_bytes())
    path.write_bytes(raw)
    forged = replace(
        evidence,
        stored_payload_sha256=hashlib.sha256(raw).hexdigest(),
        stored_payload_size_bytes=len(raw),
    )
    with pytest.raises(ValueError, match=match):
        verify_p101_retained_identity(forged)


def test_p102_rejects_incompatible_evidence_type():
    with pytest.raises(ValueError, match="incompatible type"):
        verify_p101_retained_identity(object())


def test_p102_truth_boundary_is_explicit_and_non_authoritative(tmp_path):
    evidence, _, _ = _fixture(tmp_path)
    result = verify_p101_retained_identity(evidence)
    rendered = result.as_dict()
    assert rendered["truth_boundary"] == TRUTH_BOUNDARY
    boundary = TRUTH_BOUNDARY.lower()
    for phrase in (
        "does not authenticate",
        "freshness",
        "monotonic",
        "rollback",
        "atomic snapshot",
        "authorize startup",
        "cas",
        "tpm/hsm",
        "distributed consensus",
        "production readiness",
        "benchmark evidence",
        "novelty evidence",
        "automatic-control authority",
    ):
        assert phrase in boundary
