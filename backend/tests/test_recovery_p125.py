from __future__ import annotations

import hashlib
import json

import pytest

from app.recovery_p118 import EVIDENCE_STATE as P118_EVIDENCE_STATE
from app.recovery_p120 import EVIDENCE_STATE as P120_EVIDENCE_STATE
from app.recovery_p122 import EVIDENCE_STATE as P122_EVIDENCE_STATE
from app.recovery_p123 import (
    EVIDENCE_STATE as P123_EVIDENCE_STATE,
    RecoveryP120P122CompositionEvidence,
    _FIELDS as P123_SHARED_FIELDS,
)
from app.recovery_p124 import SCHEMA as P124_SCHEMA, canonicalize_p123_composition_receipt
from app.recovery_p125 import EVIDENCE_STATE, TRUTH_BOUNDARY, _FIELDS, replay_p124_composition_receipt


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _p123(**overrides: object) -> RecoveryP120P122CompositionEvidence:
    values: dict[str, object] = {}
    n = 29
    for field, kind in _FIELDS:
        if field == "p120_p122_composition_binding_sha256":
            continue
        if kind == "int":
            values[field] = n
            n += 19
        else:
            values[field] = _sha(field)

    shared = {field: values[field] for field, _ in P123_SHARED_FIELDS}
    binding_document = {
        **shared,
        "retained_p121_record_payload_sha256": values["retained_p121_record_payload_sha256"],
        "retained_p121_record_payload_size_bytes": values["retained_p121_record_payload_size_bytes"],
        "p118_evidence_state": P118_EVIDENCE_STATE,
        "p120_evidence_state": P120_EVIDENCE_STATE,
        "p122_evidence_state": P122_EVIDENCE_STATE,
    }
    values["p120_p122_composition_binding_sha256"] = hashlib.sha256(
        json.dumps(binding_document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    values.update({"p120_contract_verified": True, "p122_contract_verified": True, "cross_evidence_identity_verified": True})
    values.update(overrides)
    return RecoveryP120P122CompositionEvidence(**values)


def _receipt_bytes(**overrides: object) -> tuple[bytes, str, int]:
    evidence = canonicalize_p123_composition_receipt(_p123(**overrides))
    return evidence.payload, evidence.payload_sha256, evidence.payload_size_bytes


def _reidentify(payload: bytes) -> tuple[str, int]:
    return hashlib.sha256(payload).hexdigest(), len(payload)


def _canonical_mutation(payload: bytes, key: str, value: object) -> tuple[bytes, str, int]:
    decoded = json.loads(payload)
    decoded[key] = value
    forged = json.dumps(decoded, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    sha, size = _reidentify(forged)
    return forged, sha, size


def test_p125_replays_real_p124_path_and_is_non_authoritative() -> None:
    payload, sha, size = _receipt_bytes()
    replay = replay_p124_composition_receipt(payload, expected_payload_sha256=sha, expected_payload_size_bytes=size)
    assert replay.evidence_state == EVIDENCE_STATE
    assert replay.automatic_control_allowed is False
    assert replay.expected_payload_identity_verified
    assert replay.canonical_receipt_verified
    assert replay.dependency_state_verified
    assert replay.p120_p122_composition_binding_recomputed_verified
    assert replay.p124_receipt_payload_sha256 == sha
    assert replay.p124_receipt_payload_size_bytes == size
    assert replay.p123_evidence_state == P123_EVIDENCE_STATE


def test_p125_rejects_wrong_expected_outer_identity() -> None:
    payload, sha, size = _receipt_bytes()
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        replay_p124_composition_receipt(payload, expected_payload_sha256=_sha("wrong"), expected_payload_size_bytes=size)
    with pytest.raises(ValueError, match="byte length mismatch"):
        replay_p124_composition_receipt(payload, expected_payload_sha256=sha, expected_payload_size_bytes=size + 1)


@pytest.mark.parametrize("bad_sha", ["A" * 64, "0" * 63, 7])
def test_p125_rejects_invalid_expected_sha(bad_sha: object) -> None:
    payload, _, size = _receipt_bytes()
    with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
        replay_p124_composition_receipt(
            payload, expected_payload_sha256=bad_sha, expected_payload_size_bytes=size  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("bad_size", [False, 0, -1])
def test_p125_rejects_invalid_expected_size(bad_size: object) -> None:
    payload, sha, _ = _receipt_bytes()
    with pytest.raises(ValueError, match="positive integer"):
        replay_p124_composition_receipt(
            payload, expected_payload_sha256=sha, expected_payload_size_bytes=bad_size  # type: ignore[arg-type]
        )


def test_p125_rejects_non_bytes_payload() -> None:
    with pytest.raises(ValueError, match="must be bytes"):
        replay_p124_composition_receipt(
            "{}", expected_payload_sha256="0" * 64, expected_payload_size_bytes=2  # type: ignore[arg-type]
        )


def test_p125_rejects_noncanonical_json_even_when_outer_identity_matches() -> None:
    payload, _, _ = _receipt_bytes()
    decoded = json.loads(payload)
    noncanonical = json.dumps(decoded, indent=2, sort_keys=False).encode()
    sha, size = _reidentify(noncanonical)
    with pytest.raises(ValueError, match="strict canonical JSON"):
        replay_p124_composition_receipt(noncanonical, expected_payload_sha256=sha, expected_payload_size_bytes=size)


def test_p125_rejects_schema_and_state_drift_with_recomputed_outer_identity() -> None:
    payload, _, _ = _receipt_bytes()
    for key, value in (("schema", P124_SCHEMA + ".forged"), ("p123_evidence_state", "forged")):
        forged, sha, size = _canonical_mutation(payload, key, value)
        with pytest.raises(ValueError):
            replay_p124_composition_receipt(forged, expected_payload_sha256=sha, expected_payload_size_bytes=size)


def test_p125_rejects_extra_and_missing_schema_keys() -> None:
    payload, _, _ = _receipt_bytes()
    decoded = json.loads(payload)
    decoded["extra"] = "forged"
    forged = json.dumps(decoded, sort_keys=True, separators=(",", ":")).encode()
    sha, size = _reidentify(forged)
    with pytest.raises(ValueError, match="schema"):
        replay_p124_composition_receipt(forged, expected_payload_sha256=sha, expected_payload_size_bytes=size)

    decoded = json.loads(payload)
    decoded.pop(next(field for field, _ in _FIELDS))
    forged = json.dumps(decoded, sort_keys=True, separators=(",", ":")).encode()
    sha, size = _reidentify(forged)
    with pytest.raises(ValueError, match="schema"):
        replay_p124_composition_receipt(forged, expected_payload_sha256=sha, expected_payload_size_bytes=size)


@pytest.mark.parametrize("field", [field for field, kind in _FIELDS if kind == "int"])
@pytest.mark.parametrize("bad", [False, 0, -1])
def test_p125_rejects_invalid_integer_identity_across_every_serialized_field(field: str, bad: object) -> None:
    payload, _, _ = _receipt_bytes()
    forged, sha, size = _canonical_mutation(payload, field, bad)
    with pytest.raises(ValueError, match="positive integer"):
        replay_p124_composition_receipt(forged, expected_payload_sha256=sha, expected_payload_size_bytes=size)


@pytest.mark.parametrize("field", [field for field, kind in _FIELDS if kind == "sha"])
@pytest.mark.parametrize("bad", ["A" * 64, "f" * 63, "g" * 64])
def test_p125_rejects_invalid_sha_identity_across_every_serialized_field(field: str, bad: object) -> None:
    payload, _, _ = _receipt_bytes()
    forged, sha, size = _canonical_mutation(payload, field, bad)
    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        replay_p124_composition_receipt(forged, expected_payload_sha256=sha, expected_payload_size_bytes=size)


@pytest.mark.parametrize("field,kind", _FIELDS)
def test_p125_rejects_semantic_tampering_when_outer_identity_is_recomputed(field: str, kind: str) -> None:
    payload, _, _ = _receipt_bytes()
    decoded = json.loads(payload)
    replacement = decoded[field] + 1 if kind == "int" else _sha("tampered-" + field)
    forged, sha, size = _canonical_mutation(payload, field, replacement)
    with pytest.raises(ValueError, match="composition binding recomputation mismatch"):
        replay_p124_composition_receipt(forged, expected_payload_sha256=sha, expected_payload_size_bytes=size)


def test_p125_rejects_forged_composition_binding_with_recomputed_outer_identity() -> None:
    payload, _, _ = _receipt_bytes()
    forged, sha, size = _canonical_mutation(payload, "p120_p122_composition_binding_sha256", _sha("forged-binding"))
    with pytest.raises(ValueError, match="composition binding recomputation mismatch"):
        replay_p124_composition_receipt(forged, expected_payload_sha256=sha, expected_payload_size_bytes=size)


@pytest.mark.parametrize(
    "payload",
    [
        b"\xff",
        b"{",
        b"[]",
    ],
)
def test_p125_rejects_invalid_utf8_json_or_non_object_payload(payload: bytes) -> None:
    sha, size = _reidentify(payload)
    with pytest.raises(ValueError):
        replay_p124_composition_receipt(payload, expected_payload_sha256=sha, expected_payload_size_bytes=size)


def test_p125_truth_boundary_is_explicit() -> None:
    assert "does not authenticate" in TRUTH_BOUNDARY
    assert "freshness/latest/global/monotonic" in TRUTH_BOUNDARY
    assert "prevent replay or coordinated rollback" in TRUTH_BOUNDARY
    assert "authorize startup or mutation" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark evidence" in TRUTH_BOUNDARY
    assert "novelty evidence" in TRUTH_BOUNDARY
    assert "automatic-control authority" in TRUTH_BOUNDARY
