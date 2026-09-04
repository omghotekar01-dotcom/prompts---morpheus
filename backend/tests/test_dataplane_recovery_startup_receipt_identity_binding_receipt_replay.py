from __future__ import annotations

import hashlib
import json

import pytest

from app.dataplane_recovery_startup_receipt_identity_binding import (
    EVIDENCE_STATE as P78_EVIDENCE_STATE,
    RecoveryStartupStoredReceiptBindingEvidence,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt import (
    encode_recovery_startup_stored_receipt_binding_receipt,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    replay_recovery_startup_stored_receipt_binding_receipt,
)
from app.dataplane_recovery_startup_receipt_identity_replay import (
    EVIDENCE_STATE as P77_EVIDENCE_STATE,
)
from app.dataplane_recovery_startup_receipt_replay import (
    EVIDENCE_STATE as P75_EVIDENCE_STATE,
)


def _canonical(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _binding(payload: dict[str, object]) -> str:
    binding_payload = {
        "sequence": payload["sequence"],
        "lineage_sha256": payload["lineage_sha256"],
        "receipt_payload_sha256": payload["receipt_payload_sha256"],
        "receipt_payload_size_bytes": payload["receipt_payload_size_bytes"],
        "admission_binding_sha256": payload["admission_binding_sha256"],
        "stored_identity_payload_sha256": payload["stored_identity_payload_sha256"],
        "stored_identity_payload_size_bytes": payload[
            "stored_identity_payload_size_bytes"
        ],
        "p75_evidence_state": P75_EVIDENCE_STATE,
        "p77_evidence_state": P77_EVIDENCE_STATE,
    }
    return hashlib.sha256(_canonical(binding_payload)).hexdigest()


def _payload() -> dict[str, object]:
    payload: dict[str, object] = {
        "admission_binding_sha256": "c" * 64,
        "lineage_sha256": "a" * 64,
        "p78_evidence_state": P78_EVIDENCE_STATE,
        "receipt_identity_binding_sha256": "",
        "receipt_payload_sha256": "b" * 64,
        "receipt_payload_size_bytes": 321,
        "sequence": 7,
        "stored_identity_payload_sha256": "d" * 64,
        "stored_identity_payload_size_bytes": 256,
    }
    payload["receipt_identity_binding_sha256"] = _binding(payload)
    return payload


def _replay(raw: bytes):
    return replay_recovery_startup_stored_receipt_binding_receipt(
        raw,
        expected_payload_sha256=hashlib.sha256(raw).hexdigest(),
        expected_payload_size_bytes=len(raw),
    )


def test_p80_replays_exact_canonical_p79_binding_receipt() -> None:
    raw = _canonical(_payload())

    evidence = _replay(raw)

    assert evidence.evidence_state == EVIDENCE_STATE
    assert evidence.sequence == 7
    assert evidence.lineage_sha256 == "a" * 64
    assert evidence.receipt_payload_sha256 == "b" * 64
    assert evidence.receipt_payload_size_bytes == 321
    assert evidence.admission_binding_sha256 == "c" * 64
    assert evidence.stored_identity_payload_sha256 == "d" * 64
    assert evidence.stored_identity_payload_size_bytes == 256
    assert evidence.receipt_identity_binding_sha256 == _payload()[
        "receipt_identity_binding_sha256"
    ]
    assert evidence.binding_receipt_payload_sha256 == hashlib.sha256(raw).hexdigest()
    assert evidence.binding_receipt_payload_size_bytes == len(raw)
    assert evidence.expected_payload_identity_verified is True
    assert evidence.canonical_receipt_verified is True
    assert evidence.dependency_state_verified is True
    assert evidence.receipt_identity_binding_recomputed_verified is True
    assert evidence.p78_evidence_state == P78_EVIDENCE_STATE
    assert evidence.automatic_control_allowed is False


def test_p80_accepts_real_p79_encoder_output_end_to_end() -> None:
    p78 = RecoveryStartupStoredReceiptBindingEvidence(
        sequence=7,
        lineage_sha256="a" * 64,
        receipt_payload_sha256="b" * 64,
        receipt_payload_size_bytes=321,
        admission_binding_sha256="c" * 64,
        stored_identity_payload_sha256="d" * 64,
        stored_identity_payload_size_bytes=256,
        receipt_identity_binding_sha256=_payload()["receipt_identity_binding_sha256"],
        p75_contract_verified=True,
        p77_contract_verified=True,
        cross_evidence_identity_verified=True,
    )
    p79 = encode_recovery_startup_stored_receipt_binding_receipt(p78)

    replayed = replay_recovery_startup_stored_receipt_binding_receipt(
        p79.binding_receipt_payload_utf8,
        expected_payload_sha256=p79.binding_receipt_payload_sha256,
        expected_payload_size_bytes=p79.binding_receipt_payload_size_bytes,
    )

    assert replayed.sequence == p79.sequence
    assert replayed.lineage_sha256 == p79.lineage_sha256
    assert replayed.receipt_identity_binding_sha256 == p79.receipt_identity_binding_sha256
    assert replayed.binding_receipt_payload_sha256 == p79.binding_receipt_payload_sha256
    assert replayed.binding_receipt_payload_size_bytes == p79.binding_receipt_payload_size_bytes
    assert replayed.receipt_identity_binding_recomputed_verified is True


def test_p80_rejects_wrong_expected_size_before_semantic_acceptance() -> None:
    raw = _canonical(_payload())
    with pytest.raises(ValueError, match="byte length mismatch"):
        replay_recovery_startup_stored_receipt_binding_receipt(
            raw,
            expected_payload_sha256=hashlib.sha256(raw).hexdigest(),
            expected_payload_size_bytes=len(raw) + 1,
        )


def test_p80_rejects_wrong_expected_sha_before_semantic_acceptance() -> None:
    raw = _canonical(_payload())
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        replay_recovery_startup_stored_receipt_binding_receipt(
            raw,
            expected_payload_sha256="0" * 64,
            expected_payload_size_bytes=len(raw),
        )


@pytest.mark.parametrize(
    ("expected_sha", "expected_size"),
    [
        ("A" * 64, 1),
        ("g" * 64, 1),
        ("0" * 63, 1),
        ("0" * 64, True),
        ("0" * 64, 0),
    ],
)
def test_p80_rejects_malformed_expected_identity(expected_sha, expected_size) -> None:
    with pytest.raises(ValueError):
        replay_recovery_startup_stored_receipt_binding_receipt(
            b"x",
            expected_payload_sha256=expected_sha,
            expected_payload_size_bytes=expected_size,
        )


def test_p80_rejects_non_bytes_payload() -> None:
    with pytest.raises(ValueError, match="must be bytes"):
        replay_recovery_startup_stored_receipt_binding_receipt(
            "{}",  # type: ignore[arg-type]
            expected_payload_sha256="0" * 64,
            expected_payload_size_bytes=2,
        )


@pytest.mark.parametrize(
    "raw",
    [
        b"\xff",
        b"{",
        b"[]",
    ],
)
def test_p80_rejects_invalid_encoding_json_or_shape(raw: bytes) -> None:
    with pytest.raises(ValueError):
        _replay(raw)


def test_p80_rejects_noncanonical_json_even_with_matching_expected_identity() -> None:
    raw = json.dumps(_payload(), sort_keys=False, indent=2).encode("utf-8")
    with pytest.raises(ValueError, match="canonical"):
        _replay(raw)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda p: p.update({"extra": 1}),
        lambda p: p.pop("sequence"),
    ],
)
def test_p80_rejects_schema_drift(mutator) -> None:
    payload = _payload()
    mutator(payload)
    with pytest.raises(ValueError, match="schema"):
        _replay(_canonical(payload))


@pytest.mark.parametrize(
    "mutation",
    [
        {"p78_evidence_state": "WRONG"},
        {"sequence": True},
        {"sequence": 0},
        {"lineage_sha256": "A" * 64},
        {"receipt_payload_sha256": "g" * 64},
        {"receipt_payload_size_bytes": 0},
        {"admission_binding_sha256": "0" * 63},
        {"stored_identity_payload_sha256": "f" * 63},
        {"stored_identity_payload_size_bytes": 0},
    ],
)
def test_p80_rejects_invalid_serialized_semantics(mutation) -> None:
    payload = _payload()
    payload.update(mutation)
    with pytest.raises(ValueError):
        _replay(_canonical(payload))


def test_p80_rejects_forged_serialized_p78_binding() -> None:
    payload = _payload()
    payload["receipt_identity_binding_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="recomputation mismatch"):
        _replay(_canonical(payload))


def test_p80_binding_recomputation_is_sensitive_to_serialized_identity() -> None:
    payload = _payload()
    payload["sequence"] = 8
    # Preserve the old valid binding deliberately; changing a semantic identity
    # without updating the P78 binding must fail independently of outer byte identity.
    with pytest.raises(ValueError, match="recomputation mismatch"):
        _replay(_canonical(payload))


def test_p80_is_replay_evidence_not_freshness_or_startup_authority() -> None:
    evidence = _replay(_canonical(_payload()))

    assert evidence.automatic_control_allowed is False
    assert "read-only" in TRUTH_BOUNDARY
    assert "expected byte identity" in TRUTH_BOUNDARY
    assert "freshness" in TRUTH_BOUNDARY
    assert "replay" in TRUTH_BOUNDARY
    assert "authorize startup" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark" in TRUTH_BOUNDARY
    assert "novelty" in TRUTH_BOUNDARY
