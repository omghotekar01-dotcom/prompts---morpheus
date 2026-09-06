from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.recovery_p108 import EVIDENCE_STATE as P108_EVIDENCE_STATE
from app.recovery_p110 import EVIDENCE_STATE as P110_EVIDENCE_STATE
from app.recovery_p112 import EVIDENCE_STATE as P112_EVIDENCE_STATE
from app.recovery_p113 import RecoveryP110P112CompositionEvidence, _FIELDS as P113_SHARED_FIELDS
from app.recovery_p114 import SCHEMA as P114_SCHEMA, canonicalize_p113_composition_receipt
from app.recovery_p115 import EVIDENCE_STATE, TRUTH_BOUNDARY, _FIELDS, replay_p114_composition_receipt


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _p113(**overrides: object) -> RecoveryP110P112CompositionEvidence:
    values: dict[str, object] = {}
    n = 17
    for field, kind in _FIELDS:
        if field == "p110_p112_composition_binding_sha256":
            continue
        if kind == "int":
            values[field] = n
            n += 13
        else:
            values[field] = _sha(field)
    shared = {field: values[field] for field, _ in P113_SHARED_FIELDS}
    binding_document = {
        **shared,
        "retained_p111_record_payload_sha256": values["retained_p111_record_payload_sha256"],
        "retained_p111_record_payload_size_bytes": values["retained_p111_record_payload_size_bytes"],
        "p108_evidence_state": P108_EVIDENCE_STATE,
        "p110_evidence_state": P110_EVIDENCE_STATE,
        "p112_evidence_state": P112_EVIDENCE_STATE,
    }
    values["p110_p112_composition_binding_sha256"] = hashlib.sha256(
        json.dumps(binding_document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    values.update({"p110_contract_verified": True, "p112_contract_verified": True, "cross_evidence_identity_verified": True})
    values.update(overrides)
    return RecoveryP110P112CompositionEvidence(**values)


def _receipt_bytes(**overrides: object) -> tuple[bytes, str, int]:
    evidence = canonicalize_p113_composition_receipt(_p113(**overrides))
    return evidence.payload, evidence.payload_sha256, evidence.payload_size_bytes


def _reidentify(payload: bytes) -> tuple[str, int]:
    return hashlib.sha256(payload).hexdigest(), len(payload)


def test_p115_replays_real_p114_path_and_is_non_authoritative() -> None:
    payload, sha, size = _receipt_bytes()
    replay = replay_p114_composition_receipt(payload, expected_payload_sha256=sha, expected_payload_size_bytes=size)
    assert replay.evidence_state == EVIDENCE_STATE
    assert replay.automatic_control_allowed is False
    assert replay.expected_payload_identity_verified
    assert replay.canonical_receipt_verified
    assert replay.dependency_state_verified
    assert replay.p110_p112_composition_binding_recomputed_verified
    assert replay.p114_receipt_payload_sha256 == sha
    assert replay.p114_receipt_payload_size_bytes == size


def test_p115_rejects_wrong_expected_outer_identity() -> None:
    payload, sha, size = _receipt_bytes()
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        replay_p114_composition_receipt(payload, expected_payload_sha256=_sha("wrong"), expected_payload_size_bytes=size)
    with pytest.raises(ValueError, match="byte length mismatch"):
        replay_p114_composition_receipt(payload, expected_payload_sha256=sha, expected_payload_size_bytes=size + 1)


@pytest.mark.parametrize("bad_sha", ["A" * 64, "0" * 63, 7])
def test_p115_rejects_invalid_expected_sha(bad_sha: object) -> None:
    payload, _, size = _receipt_bytes()
    with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
        replay_p114_composition_receipt(payload, expected_payload_sha256=bad_sha, expected_payload_size_bytes=size)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_size", [False, 0, -1])
def test_p115_rejects_invalid_expected_size(bad_size: object) -> None:
    payload, sha, _ = _receipt_bytes()
    with pytest.raises(ValueError, match="positive integer"):
        replay_p114_composition_receipt(payload, expected_payload_sha256=sha, expected_payload_size_bytes=bad_size)  # type: ignore[arg-type]


def test_p115_rejects_non_bytes_payload() -> None:
    with pytest.raises(ValueError, match="must be bytes"):
        replay_p114_composition_receipt("{}", expected_payload_sha256="0" * 64, expected_payload_size_bytes=2)  # type: ignore[arg-type]


def test_p115_rejects_noncanonical_json_even_when_outer_identity_matches() -> None:
    payload, _, _ = _receipt_bytes()
    decoded = json.loads(payload)
    noncanonical = json.dumps(decoded, indent=2, sort_keys=False).encode()
    sha, size = _reidentify(noncanonical)
    with pytest.raises(ValueError, match="strict canonical JSON"):
        replay_p114_composition_receipt(noncanonical, expected_payload_sha256=sha, expected_payload_size_bytes=size)


def test_p115_rejects_schema_and_state_drift_with_recomputed_outer_identity() -> None:
    payload, _, _ = _receipt_bytes()
    for key, value in (("schema", P114_SCHEMA + ".forged"), ("p113_evidence_state", "forged")):
        decoded = json.loads(payload)
        decoded[key] = value
        forged = json.dumps(decoded, sort_keys=True, separators=(",", ":")).encode()
        sha, size = _reidentify(forged)
        with pytest.raises(ValueError):
            replay_p114_composition_receipt(forged, expected_payload_sha256=sha, expected_payload_size_bytes=size)


def test_p115_rejects_extra_or_missing_schema_keys() -> None:
    payload, _, _ = _receipt_bytes()
    for mutate in (lambda d: d.update({"extra": 1}), lambda d: d.pop("lineage_sha256")):
        decoded = json.loads(payload)
        mutate(decoded)
        forged = json.dumps(decoded, sort_keys=True, separators=(",", ":")).encode()
        sha, size = _reidentify(forged)
        with pytest.raises(ValueError, match="schema"):
            replay_p114_composition_receipt(forged, expected_payload_sha256=sha, expected_payload_size_bytes=size)


@pytest.mark.parametrize("field,kind", _FIELDS)
def test_p115_validates_every_serialized_identity(field: str, kind: str) -> None:
    payload, _, _ = _receipt_bytes()
    decoded = json.loads(payload)
    decoded[field] = False if kind == "int" else "A" * 64
    forged = json.dumps(decoded, sort_keys=True, separators=(",", ":")).encode()
    sha, size = _reidentify(forged)
    with pytest.raises(ValueError):
        replay_p114_composition_receipt(forged, expected_payload_sha256=sha, expected_payload_size_bytes=size)


@pytest.mark.parametrize("field,kind", tuple(item for item in _FIELDS if item[0] != "p110_p112_composition_binding_sha256"))
def test_p115_rejects_semantic_tampering_even_with_recomputed_outer_identity(field: str, kind: str) -> None:
    payload, _, _ = _receipt_bytes()
    decoded = json.loads(payload)
    decoded[field] = decoded[field] + 1 if kind == "int" else _sha("tampered-" + field)
    forged = json.dumps(decoded, sort_keys=True, separators=(",", ":")).encode()
    sha, size = _reidentify(forged)
    with pytest.raises(ValueError, match="binding recomputation mismatch"):
        replay_p114_composition_receipt(forged, expected_payload_sha256=sha, expected_payload_size_bytes=size)


def test_p115_rejects_forged_binding_even_with_recomputed_outer_identity() -> None:
    payload, _, _ = _receipt_bytes()
    decoded = json.loads(payload)
    decoded["p110_p112_composition_binding_sha256"] = _sha("forged-binding")
    forged = json.dumps(decoded, sort_keys=True, separators=(",", ":")).encode()
    sha, size = _reidentify(forged)
    with pytest.raises(ValueError, match="binding recomputation mismatch"):
        replay_p114_composition_receipt(forged, expected_payload_sha256=sha, expected_payload_size_bytes=size)


@pytest.mark.parametrize("payload", [b"\xff", b"not-json", b"[]"])
def test_p115_rejects_invalid_utf8_json_and_non_object(payload: bytes) -> None:
    sha, size = _reidentify(payload)
    with pytest.raises(ValueError):
        replay_p114_composition_receipt(payload, expected_payload_sha256=sha, expected_payload_size_bytes=size)


def test_p115_truth_boundary_is_explicit() -> None:
    assert "does not authenticate" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark evidence" in TRUTH_BOUNDARY
    assert "novelty evidence" in TRUTH_BOUNDARY
    assert "automatic-control authority" in TRUTH_BOUNDARY
