from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.recovery_p120 import EVIDENCE_STATE as P120_EVIDENCE_STATE
from app.recovery_p121 import EVIDENCE_STATE as P121_EVIDENCE_STATE, RecoveryP120ReplayIdentityStoreEvidence
from app.recovery_p122 import EVIDENCE_STATE, TRUTH_BOUNDARY, _FIELDS, verify_p121_retained_identity


def _sha(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _canonical(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _fixture(tmp_path):
    values: dict[str, object] = {}
    size = 701
    sha_index = 0
    for field, kind in _FIELDS:
        if kind == "sha":
            sha_index += 1
            values[field] = _sha(f"p122-{sha_index}")
        else:
            values[field] = 43 if field == "sequence" else size
            size += 1

    payload = {field: values[field] for field, _ in _FIELDS}
    payload["p120_evidence_state"] = P120_EVIDENCE_STATE
    encoded = _canonical(payload)
    path = tmp_path / "p121.json"
    path.write_bytes(encoded)
    evidence = RecoveryP120ReplayIdentityStoreEvidence(
        **values,
        stored_payload_sha256=hashlib.sha256(encoded).hexdigest(),
        stored_payload_size_bytes=len(encoded),
        destination_path=str(path),
        p120_evidence_state_verified=True,
        p120_verification_flags_verified=True,
        exact_readback_verified=True,
    )
    return evidence, path, payload


def _rewrite(evidence, path, payload):
    encoded = _canonical(payload)
    path.write_bytes(encoded)
    return replace(
        evidence,
        stored_payload_sha256=hashlib.sha256(encoded).hexdigest(),
        stored_payload_size_bytes=len(encoded),
    )


def test_p122_verifies_canonical_p121_record(tmp_path):
    evidence, path, _ = _fixture(tmp_path)
    result = verify_p121_retained_identity(evidence)
    assert result.source_path == str(path)
    assert result.evidence_state == EVIDENCE_STATE
    assert result.automatic_control_allowed is False
    assert result.p121_evidence_state_verified is True
    assert result.p121_verification_flags_verified is True
    assert result.exact_payload_identity_verified is True
    assert result.canonical_record_verified is True
    assert result.semantic_agreement_verified is True
    for field, _ in _FIELDS:
        assert getattr(result, field) == getattr(evidence, field)


def test_p122_supports_explicit_alternate_source(tmp_path):
    evidence, _, payload = _fixture(tmp_path)
    alternate = tmp_path / "archive" / "p121.json"
    alternate.parent.mkdir()
    alternate.write_bytes(_canonical(payload))
    result = verify_p121_retained_identity(evidence, source_path=alternate)
    assert result.source_path == str(alternate)


@pytest.mark.parametrize(
    "flag",
    ["p120_evidence_state_verified", "p120_verification_flags_verified", "exact_readback_verified"],
)
def test_p122_rejects_weakened_p121_verification_flags(tmp_path, flag):
    evidence, _, _ = _fixture(tmp_path)
    with pytest.raises(ValueError, match="verification flags"):
        verify_p121_retained_identity(replace(evidence, **{flag: False}))


def test_p122_rejects_p121_state_drift_and_automatic_control_escalation(tmp_path):
    evidence, _, _ = _fixture(tmp_path)
    with pytest.raises(ValueError, match="state is incompatible"):
        verify_p121_retained_identity(replace(evidence, evidence_state=P121_EVIDENCE_STATE + "_DRIFT"))
    with pytest.raises(ValueError, match="automatic-control"):
        verify_p121_retained_identity(replace(evidence, automatic_control_allowed=True))


@pytest.mark.parametrize("field,kind", _FIELDS)
def test_p122_rejects_invalid_evidence_identities(tmp_path, field, kind):
    evidence, _, _ = _fixture(tmp_path)
    bad = True if kind == "int" else "A" * 64
    match = "positive integer" if kind == "int" else "64 lowercase hexadecimal"
    with pytest.raises(ValueError, match=match):
        verify_p121_retained_identity(replace(evidence, **{field: bad}))


def test_p122_rejects_stored_size_drift(tmp_path):
    evidence, _, _ = _fixture(tmp_path)
    with pytest.raises(ValueError, match="byte length mismatch"):
        verify_p121_retained_identity(replace(evidence, stored_payload_size_bytes=evidence.stored_payload_size_bytes + 1))


def test_p122_rejects_same_size_byte_tampering(tmp_path):
    evidence, path, _ = _fixture(tmp_path)
    raw = bytearray(path.read_bytes())
    raw[-2] = ord("1") if raw[-2] != ord("1") else ord("2")
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_p121_retained_identity(evidence)


def test_p122_rejects_noncanonical_json_even_with_recomputed_outer_identity(tmp_path):
    evidence, path, payload = _fixture(tmp_path)
    encoded = json.dumps(payload, sort_keys=False, indent=2).encode("utf-8")
    path.write_bytes(encoded)
    evidence = replace(
        evidence,
        stored_payload_sha256=hashlib.sha256(encoded).hexdigest(),
        stored_payload_size_bytes=len(encoded),
    )
    with pytest.raises(ValueError, match="strict canonical JSON"):
        verify_p121_retained_identity(evidence)


def test_p122_rejects_schema_and_embedded_state_drift(tmp_path):
    evidence, path, payload = _fixture(tmp_path)
    extra = dict(payload)
    extra["unexpected"] = 1
    with pytest.raises(ValueError, match="schema is incompatible"):
        verify_p121_retained_identity(_rewrite(evidence, path, extra))

    drift = dict(payload)
    drift["p120_evidence_state"] = P120_EVIDENCE_STATE + "_DRIFT"
    with pytest.raises(ValueError, match="incompatible P120 evidence state"):
        verify_p121_retained_identity(_rewrite(evidence, path, drift))


@pytest.mark.parametrize("field,kind", _FIELDS)
def test_p122_rejects_semantic_forgery_even_with_recomputed_record_identity(tmp_path, field, kind):
    evidence, path, payload = _fixture(tmp_path)
    forged = dict(payload)
    forged[field] = forged[field] + 1 if kind == "int" else _sha(f"forged-{field}")
    rewritten = _rewrite(evidence, path, forged)
    with pytest.raises(ValueError, match=f"disagrees on {field}"):
        verify_p121_retained_identity(rewritten)


@pytest.mark.parametrize("raw,match", [(b"\xff", "valid UTF-8"), (b"{", "valid JSON"), (b"[]", "JSON object")])
def test_p122_rejects_invalid_serialized_forms(tmp_path, raw, match):
    evidence, path, _ = _fixture(tmp_path)
    path.write_bytes(raw)
    evidence = replace(
        evidence,
        stored_payload_sha256=hashlib.sha256(raw).hexdigest(),
        stored_payload_size_bytes=len(raw),
    )
    with pytest.raises(ValueError, match=match):
        verify_p121_retained_identity(evidence)


def test_p122_rejects_incompatible_evidence_type(tmp_path):
    with pytest.raises(ValueError, match="incompatible type"):
        verify_p121_retained_identity(object(), source_path=tmp_path / "x")


def test_p122_truth_boundary_stays_historical_and_non_authoritative(tmp_path):
    evidence, _, _ = _fixture(tmp_path)
    result = verify_p121_retained_identity(evidence)
    published = result.as_dict()
    assert published["automatic_control_allowed"] is False
    assert published["truth_boundary"] == TRUTH_BOUNDARY
    lower = TRUTH_BOUNDARY.lower()
    for phrase in (
        "does not authenticate",
        "freshness/latest/global/monotonic",
        "authorize startup or mutation",
        "production readiness",
        "benchmark evidence",
        "novelty evidence",
        "automatic-control authority",
    ):
        assert phrase in lower
