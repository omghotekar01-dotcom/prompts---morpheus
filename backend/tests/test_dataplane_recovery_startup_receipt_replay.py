from __future__ import annotations

import hashlib
import json

import pytest

from app.dataplane_recovery_anchor_rebootstrap import EVIDENCE_STATE as P67_EVIDENCE_STATE
from app.dataplane_recovery_anchor_repeat_observation import (
    EVIDENCE_STATE as P72_EVIDENCE_STATE,
)
from app.dataplane_recovery_startup_receipt_replay import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    verify_recovery_startup_admission_receipt,
)


def _canonical(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _payload() -> dict[str, object]:
    binding_payload = {
        "sequence": 2,
        "lineage_sha256": "a" * 64,
        "p67_binding_sha256": "b" * 64,
        "observed_anchor_payload_sha256": "c" * 64,
        "observed_anchor_payload_size_bytes": 96,
        "p67_evidence_state": P67_EVIDENCE_STATE,
        "p72_evidence_state": P72_EVIDENCE_STATE,
    }
    admission_binding = hashlib.sha256(_canonical(binding_payload)).hexdigest()
    return {
        "admission_binding_sha256": admission_binding,
        "lineage_sha256": "a" * 64,
        "observed_anchor_payload_sha256": "c" * 64,
        "observed_anchor_payload_size_bytes": 96,
        "p67_binding_sha256": "b" * 64,
        "p67_evidence_state": P67_EVIDENCE_STATE,
        "p72_evidence_state": P72_EVIDENCE_STATE,
        "sequence": 2,
    }


def _verify(encoded: bytes):
    return verify_recovery_startup_admission_receipt(
        encoded,
        expected_payload_sha256=hashlib.sha256(encoded).hexdigest(),
        expected_payload_size_bytes=len(encoded),
    )


def test_p75_verifies_exact_canonical_receipt_and_recomputes_p73_binding() -> None:
    encoded = _canonical(_payload())
    evidence = _verify(encoded)

    assert evidence.evidence_state == EVIDENCE_STATE
    assert evidence.sequence == 2
    assert evidence.lineage_sha256 == "a" * 64
    assert evidence.receipt_payload_sha256 == hashlib.sha256(encoded).hexdigest()
    assert evidence.receipt_payload_size_bytes == len(encoded)
    assert evidence.expected_payload_identity_verified is True
    assert evidence.canonical_receipt_verified is True
    assert evidence.admission_binding_recomputed_verified is True
    assert evidence.dependency_states_verified is True
    assert evidence.automatic_control_allowed is False
    assert evidence.as_dict()["truth_boundary"] == TRUTH_BOUNDARY


def test_p75_rejects_wrong_expected_byte_identity() -> None:
    encoded = _canonical(_payload())
    with pytest.raises(ValueError, match="size"):
        verify_recovery_startup_admission_receipt(
            encoded,
            expected_payload_sha256=hashlib.sha256(encoded).hexdigest(),
            expected_payload_size_bytes=len(encoded) + 1,
        )
    with pytest.raises(ValueError, match="SHA-256"):
        verify_recovery_startup_admission_receipt(
            encoded,
            expected_payload_sha256="0" * 64,
            expected_payload_size_bytes=len(encoded),
        )


@pytest.mark.parametrize(
    "mutator",
    [
        lambda p: {**p, "sequence": True},
        lambda p: {**p, "lineage_sha256": "A" * 64},
        lambda p: {**p, "p67_binding_sha256": "0" * 63},
        lambda p: {**p, "observed_anchor_payload_size_bytes": 0},
        lambda p: {**p, "p67_evidence_state": "WRONG"},
        lambda p: {**p, "p72_evidence_state": "WRONG"},
    ],
)
def test_p75_rejects_invalid_receipt_semantics(mutator) -> None:
    with pytest.raises(ValueError):
        _verify(_canonical(mutator(_payload())))


def test_p75_rejects_receipt_when_admission_binding_does_not_recompute() -> None:
    payload = _payload()
    payload["admission_binding_sha256"] = "d" * 64
    with pytest.raises(ValueError, match="does not recompute"):
        _verify(_canonical(payload))


def test_p75_rejects_noncanonical_or_schema_drift() -> None:
    payload = _payload()
    pretty = json.dumps(payload, sort_keys=True, indent=2).encode("utf-8")
    with pytest.raises(ValueError, match="not strict canonical JSON"):
        _verify(pretty)

    extra = {**payload, "extra": "unsupported"}
    with pytest.raises(ValueError, match="unsupported schema"):
        _verify(_canonical(extra))

    missing = dict(payload)
    del missing["p72_evidence_state"]
    with pytest.raises(ValueError, match="unsupported schema"):
        _verify(_canonical(missing))


@pytest.mark.parametrize(
    "encoded",
    [
        b"[]",
        b"{",
        b"\xff",
    ],
)
def test_p75_rejects_non_object_malformed_or_non_utf8_payloads(encoded: bytes) -> None:
    with pytest.raises(ValueError):
        _verify(encoded)


def test_p75_rejects_invalid_expected_identity_types() -> None:
    encoded = _canonical(_payload())
    with pytest.raises(ValueError):
        verify_recovery_startup_admission_receipt(
            encoded,
            expected_payload_sha256="A" * 64,
            expected_payload_size_bytes=len(encoded),
        )
    with pytest.raises(ValueError):
        verify_recovery_startup_admission_receipt(
            encoded,
            expected_payload_sha256=hashlib.sha256(encoded).hexdigest(),
            expected_payload_size_bytes=True,
        )
    with pytest.raises(ValueError):
        verify_recovery_startup_admission_receipt(
            bytearray(encoded),  # type: ignore[arg-type]
            expected_payload_sha256=hashlib.sha256(encoded).hexdigest(),
            expected_payload_size_bytes=len(encoded),
        )


def test_p75_is_replay_consistency_evidence_not_freshness_or_startup_authority() -> None:
    encoded = _canonical(_payload())
    first = _verify(encoded)
    repeated = _verify(encoded)

    # An old internally valid receipt can be replayed if the caller also supplies
    # its matching expected identity. P75 intentionally cannot establish whether
    # that identity is the latest independently trusted one.
    assert first == repeated
    assert first.automatic_control_allowed is False
    assert "does not authenticate" in TRUTH_BOUNDARY
    assert "freshness" in TRUTH_BOUNDARY
    assert "rollback or replay" in TRUTH_BOUNDARY
    assert "authorize startup" in TRUTH_BOUNDARY
    assert "benchmark" in TRUTH_BOUNDARY
