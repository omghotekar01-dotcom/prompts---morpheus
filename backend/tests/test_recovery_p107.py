from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.recovery_p105 import EVIDENCE_STATE as P105_EVIDENCE_STATE
from app.recovery_p106 import EVIDENCE_STATE as P106_EVIDENCE_STATE, RecoveryP105ReplayIdentityStoreEvidence
from app.recovery_p107 import EVIDENCE_STATE, TRUTH_BOUNDARY, _FIELDS, verify_p106_retained_identity


def _sha(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _canonical(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _fixture(tmp_path):
    values: dict[str, object] = {}
    size = 401
    sha_index = 0
    for field, kind in _FIELDS:
        if kind == "sha":
            sha_index += 1
            values[field] = _sha(f"p107-{sha_index}")
        else:
            values[field] = 31 if field == "sequence" else size
            size += 1

    payload = {field: values[field] for field, _ in _FIELDS}
    payload["p105_evidence_state"] = P105_EVIDENCE_STATE
    encoded = _canonical(payload)
    path = tmp_path / "p106.json"
    path.write_bytes(encoded)
    evidence = RecoveryP105ReplayIdentityStoreEvidence(
        **values,
        stored_payload_sha256=hashlib.sha256(encoded).hexdigest(),
        stored_payload_size_bytes=len(encoded),
        destination_path=str(path),
        p105_evidence_state_verified=True,
        p105_verification_flags_verified=True,
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


def test_p107_verifies_canonical_p106_record(tmp_path):
    evidence, path, _ = _fixture(tmp_path)
    result = verify_p106_retained_identity(evidence)
    assert result.source_path == str(path)
    assert result.evidence_state == EVIDENCE_STATE
    assert result.automatic_control_allowed is False
    assert result.p106_evidence_state_verified is True
    assert result.p106_verification_flags_verified is True
    assert result.exact_payload_identity_verified is True
    assert result.canonical_record_verified is True
    assert result.semantic_agreement_verified is True
    for field, _ in _FIELDS:
        assert getattr(result, field) == getattr(evidence, field)


def test_p107_supports_explicit_alternate_source(tmp_path):
    evidence, _, payload = _fixture(tmp_path)
    alternate = tmp_path / "archive" / "p106.json"
    alternate.parent.mkdir()
    alternate.write_bytes(_canonical(payload))
    result = verify_p106_retained_identity(evidence, source_path=alternate)
    assert result.source_path == str(alternate)


@pytest.mark.parametrize(
    "flag",
    ["p105_evidence_state_verified", "p105_verification_flags_verified", "exact_readback_verified"],
)
def test_p107_rejects_weakened_p106_verification_flags(tmp_path, flag):
    evidence, _, _ = _fixture(tmp_path)
    with pytest.raises(ValueError, match="verification flags"):
        verify_p106_retained_identity(replace(evidence, **{flag: False}))


def test_p107_rejects_p106_state_drift_and_automatic_control_escalation(tmp_path):
    evidence, _, _ = _fixture(tmp_path)
    with pytest.raises(ValueError, match="state is incompatible"):
        verify_p106_retained_identity(replace(evidence, evidence_state=P106_EVIDENCE_STATE + "_DRIFT"))
    with pytest.raises(ValueError, match="automatic-control"):
        verify_p106_retained_identity(replace(evidence, automatic_control_allowed=True))


@pytest.mark.parametrize("bad", [True, 0, -1])
def test_p107_rejects_invalid_positive_integer_evidence_identity(tmp_path, bad):
    evidence, _, _ = _fixture(tmp_path)
    with pytest.raises(ValueError, match="positive integer"):
        verify_p106_retained_identity(replace(evidence, sequence=bad))


@pytest.mark.parametrize("bad", ["A" * 64, "g" * 64, "abc", 7])
def test_p107_rejects_invalid_sha_evidence_identity(tmp_path, bad):
    evidence, _, _ = _fixture(tmp_path)
    with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
        verify_p106_retained_identity(replace(evidence, lineage_sha256=bad))


def test_p107_rejects_stored_size_drift(tmp_path):
    evidence, _, _ = _fixture(tmp_path)
    with pytest.raises(ValueError, match="byte length mismatch"):
        verify_p106_retained_identity(replace(evidence, stored_payload_size_bytes=evidence.stored_payload_size_bytes + 1))


def test_p107_rejects_same_size_byte_tampering(tmp_path):
    evidence, path, _ = _fixture(tmp_path)
    raw = bytearray(path.read_bytes())
    raw[-2] = ord("1") if raw[-2] != ord("1") else ord("2")
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_p106_retained_identity(evidence)


def test_p107_rejects_noncanonical_json_even_with_recomputed_outer_identity(tmp_path):
    evidence, path, payload = _fixture(tmp_path)
    encoded = json.dumps(payload, sort_keys=False, indent=2).encode("utf-8")
    path.write_bytes(encoded)
    evidence = replace(
        evidence,
        stored_payload_sha256=hashlib.sha256(encoded).hexdigest(),
        stored_payload_size_bytes=len(encoded),
    )
    with pytest.raises(ValueError, match="strict canonical JSON"):
        verify_p106_retained_identity(evidence)


def test_p107_rejects_schema_drift_even_with_recomputed_outer_identity(tmp_path):
    evidence, path, payload = _fixture(tmp_path)
    payload["unexpected"] = "field"
    evidence = _rewrite(evidence, path, payload)
    with pytest.raises(ValueError, match="schema is incompatible"):
        verify_p106_retained_identity(evidence)


def test_p107_rejects_embedded_p105_state_drift_even_with_recomputed_outer_identity(tmp_path):
    evidence, path, payload = _fixture(tmp_path)
    payload["p105_evidence_state"] = P105_EVIDENCE_STATE + "_DRIFT"
    evidence = _rewrite(evidence, path, payload)
    with pytest.raises(ValueError, match="incompatible P105 evidence state"):
        verify_p106_retained_identity(evidence)


@pytest.mark.parametrize("field,kind", _FIELDS)
def test_p107_rejects_semantic_forgery_even_with_recomputed_outer_identity(tmp_path, field, kind):
    evidence, path, payload = _fixture(tmp_path)
    payload[field] = payload[field] + 1 if kind == "int" else _sha(f"forged-{field}")
    evidence = _rewrite(evidence, path, payload)
    with pytest.raises(ValueError, match=f"disagrees on {field}"):
        verify_p106_retained_identity(evidence)


def test_p107_rejects_invalid_retained_integer_even_with_recomputed_outer_identity(tmp_path):
    evidence, path, payload = _fixture(tmp_path)
    payload["sequence"] = True
    evidence = _rewrite(evidence, path, payload)
    with pytest.raises(ValueError, match="positive integer"):
        verify_p106_retained_identity(evidence)


def test_p107_rejects_invalid_retained_sha_even_with_recomputed_outer_identity(tmp_path):
    evidence, path, payload = _fixture(tmp_path)
    payload["lineage_sha256"] = "A" * 64
    evidence = _rewrite(evidence, path, payload)
    with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
        verify_p106_retained_identity(evidence)


@pytest.mark.parametrize(
    "raw,match",
    [
        (b"\xff", "valid UTF-8"),
        (b"{", "valid JSON"),
        (b"[]", "JSON object"),
    ],
)
def test_p107_rejects_invalid_payload_forms_with_matching_outer_identity(tmp_path, raw, match):
    evidence, path, _ = _fixture(tmp_path)
    path.write_bytes(raw)
    evidence = replace(
        evidence,
        stored_payload_sha256=hashlib.sha256(raw).hexdigest(),
        stored_payload_size_bytes=len(raw),
    )
    with pytest.raises(ValueError, match=match):
        verify_p106_retained_identity(evidence)


def test_p107_rejects_incompatible_evidence_type(tmp_path):
    with pytest.raises(ValueError, match="incompatible type"):
        verify_p106_retained_identity(object(), source_path=tmp_path / "x")


def test_p107_truth_boundary_is_explicitly_non_authoritative():
    lowered = TRUTH_BOUNDARY.lower()
    assert "historical" in lowered
    assert "does not authenticate" in lowered
    assert "freshness" in lowered
    assert "rollback" in lowered
    assert "startup" in lowered
    assert "production readiness" in lowered
    assert "benchmark" in lowered
    assert "novelty" in lowered
    assert "automatic-control authority" in lowered
