from __future__ import annotations

import hashlib
import json

import pytest

from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay import (
    EVIDENCE_STATE as P80_EVIDENCE_STATE,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay import (
    EVIDENCE_STATE as P82_EVIDENCE_STATE,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding import (
    EVIDENCE_STATE as P83_EVIDENCE_STATE,
    RecoveryStartupStoredReceiptBindingReceiptReplayStoredIdentityBindingEvidence,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt import (
    SCHEMA as P84_SCHEMA,
    canonicalize_recovery_startup_replay_stored_identity_binding_receipt,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    replay_recovery_startup_replay_stored_identity_binding_receipt,
)


def _canonical(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _binding(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        _canonical(
            {
                "sequence": payload["sequence"],
                "lineage_sha256": payload["lineage_sha256"],
                "binding_receipt_payload_sha256": payload["binding_receipt_payload_sha256"],
                "binding_receipt_payload_size_bytes": payload["binding_receipt_payload_size_bytes"],
                "receipt_identity_binding_sha256": payload["receipt_identity_binding_sha256"],
                "retained_identity_payload_sha256": payload["retained_identity_payload_sha256"],
                "retained_identity_payload_size_bytes": payload["retained_identity_payload_size_bytes"],
                "p80_evidence_state": P80_EVIDENCE_STATE,
                "p82_evidence_state": P82_EVIDENCE_STATE,
            }
        )
    ).hexdigest()


def _payload() -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": P84_SCHEMA,
        "sequence": 11,
        "lineage_sha256": "a" * 64,
        "binding_receipt_payload_sha256": "b" * 64,
        "binding_receipt_payload_size_bytes": 512,
        "receipt_identity_binding_sha256": "c" * 64,
        "retained_identity_payload_sha256": "d" * 64,
        "retained_identity_payload_size_bytes": 256,
        "replay_stored_identity_binding_sha256": "",
        "p83_evidence_state": P83_EVIDENCE_STATE,
    }
    payload["replay_stored_identity_binding_sha256"] = _binding(payload)
    return payload


def _replay(raw: bytes):
    return replay_recovery_startup_replay_stored_identity_binding_receipt(
        raw,
        expected_payload_sha256=hashlib.sha256(raw).hexdigest(),
        expected_payload_size_bytes=len(raw),
    )


def test_p85_replays_exact_canonical_p84_receipt_and_recomputes_p83_binding() -> None:
    raw = _canonical(_payload())
    evidence = _replay(raw)

    assert evidence.evidence_state == EVIDENCE_STATE
    assert evidence.sequence == 11
    assert evidence.lineage_sha256 == "a" * 64
    assert evidence.binding_receipt_payload_sha256 == "b" * 64
    assert evidence.binding_receipt_payload_size_bytes == 512
    assert evidence.receipt_identity_binding_sha256 == "c" * 64
    assert evidence.retained_identity_payload_sha256 == "d" * 64
    assert evidence.retained_identity_payload_size_bytes == 256
    assert evidence.replay_stored_identity_binding_sha256 == _payload()["replay_stored_identity_binding_sha256"]
    assert evidence.replay_binding_receipt_payload_sha256 == hashlib.sha256(raw).hexdigest()
    assert evidence.replay_binding_receipt_payload_size_bytes == len(raw)
    assert evidence.expected_payload_identity_verified is True
    assert evidence.canonical_receipt_verified is True
    assert evidence.dependency_state_verified is True
    assert evidence.replay_stored_identity_binding_recomputed_verified is True
    assert evidence.p83_evidence_state == P83_EVIDENCE_STATE
    assert evidence.automatic_control_allowed is False


def test_p85_accepts_real_p84_encoder_output_end_to_end() -> None:
    payload = _payload()
    p83 = RecoveryStartupStoredReceiptBindingReceiptReplayStoredIdentityBindingEvidence(
        sequence=payload["sequence"],
        lineage_sha256=payload["lineage_sha256"],
        binding_receipt_payload_sha256=payload["binding_receipt_payload_sha256"],
        binding_receipt_payload_size_bytes=payload["binding_receipt_payload_size_bytes"],
        receipt_identity_binding_sha256=payload["receipt_identity_binding_sha256"],
        retained_identity_payload_sha256=payload["retained_identity_payload_sha256"],
        retained_identity_payload_size_bytes=payload["retained_identity_payload_size_bytes"],
        replay_stored_identity_binding_sha256=payload["replay_stored_identity_binding_sha256"],
        p80_contract_verified=True,
        p82_contract_verified=True,
        cross_evidence_identity_verified=True,
    )
    p84 = canonicalize_recovery_startup_replay_stored_identity_binding_receipt(p83)

    replayed = replay_recovery_startup_replay_stored_identity_binding_receipt(
        p84.payload,
        expected_payload_sha256=p84.payload_sha256,
        expected_payload_size_bytes=p84.payload_size_bytes,
    )

    assert replayed.sequence == p84.sequence
    assert replayed.lineage_sha256 == p84.lineage_sha256
    assert replayed.replay_stored_identity_binding_sha256 == p84.replay_stored_identity_binding_sha256
    assert replayed.replay_binding_receipt_payload_sha256 == p84.payload_sha256
    assert replayed.replay_binding_receipt_payload_size_bytes == p84.payload_size_bytes
    assert replayed.replay_stored_identity_binding_recomputed_verified is True
    assert replayed.automatic_control_allowed is False


def test_p85_rejects_wrong_expected_size_before_semantic_acceptance() -> None:
    raw = _canonical(_payload())
    with pytest.raises(ValueError, match="byte length mismatch"):
        replay_recovery_startup_replay_stored_identity_binding_receipt(
            raw,
            expected_payload_sha256=hashlib.sha256(raw).hexdigest(),
            expected_payload_size_bytes=len(raw) + 1,
        )


def test_p85_rejects_wrong_expected_sha_before_semantic_acceptance() -> None:
    raw = _canonical(_payload())
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        replay_recovery_startup_replay_stored_identity_binding_receipt(
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
def test_p85_rejects_malformed_expected_identity(expected_sha, expected_size) -> None:
    with pytest.raises(ValueError):
        replay_recovery_startup_replay_stored_identity_binding_receipt(
            b"x",
            expected_payload_sha256=expected_sha,
            expected_payload_size_bytes=expected_size,
        )


def test_p85_rejects_non_bytes_payload() -> None:
    with pytest.raises(ValueError, match="must be bytes"):
        replay_recovery_startup_replay_stored_identity_binding_receipt(
            "{}",  # type: ignore[arg-type]
            expected_payload_sha256="0" * 64,
            expected_payload_size_bytes=2,
        )


@pytest.mark.parametrize("raw", [b"\xff", b"{", b"[]"])
def test_p85_rejects_invalid_encoding_json_or_shape(raw: bytes) -> None:
    with pytest.raises(ValueError):
        _replay(raw)


def test_p85_rejects_noncanonical_json_even_with_matching_expected_identity() -> None:
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
def test_p85_rejects_schema_shape_drift(mutator) -> None:
    payload = _payload()
    mutator(payload)
    with pytest.raises(ValueError, match="schema"):
        _replay(_canonical(payload))


def test_p85_rejects_schema_identifier_drift() -> None:
    payload = _payload()
    payload["schema"] = "morpheus.recovery.p84.wrong.v1"
    with pytest.raises(ValueError, match="schema identifier"):
        _replay(_canonical(payload))


@pytest.mark.parametrize(
    "mutation",
    [
        {"p83_evidence_state": "WRONG"},
        {"sequence": True},
        {"sequence": 0},
        {"lineage_sha256": "A" * 64},
        {"binding_receipt_payload_sha256": "g" * 64},
        {"binding_receipt_payload_size_bytes": 0},
        {"receipt_identity_binding_sha256": "0" * 63},
        {"retained_identity_payload_sha256": "f" * 63},
        {"retained_identity_payload_size_bytes": 0},
    ],
)
def test_p85_rejects_invalid_serialized_semantics(mutation) -> None:
    payload = _payload()
    payload.update(mutation)
    with pytest.raises(ValueError):
        _replay(_canonical(payload))


def test_p85_rejects_forged_serialized_p83_composition_binding() -> None:
    payload = _payload()
    payload["replay_stored_identity_binding_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="recomputation mismatch"):
        _replay(_canonical(payload))


def test_p85_recomputation_is_sensitive_to_serialized_identity() -> None:
    payload = _payload()
    payload["sequence"] = 12
    with pytest.raises(ValueError, match="recomputation mismatch"):
        _replay(_canonical(payload))


def test_p85_is_replay_evidence_not_freshness_or_startup_authority() -> None:
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
