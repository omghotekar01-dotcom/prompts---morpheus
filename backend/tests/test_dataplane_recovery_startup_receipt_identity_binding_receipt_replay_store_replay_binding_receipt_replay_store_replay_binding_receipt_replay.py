from __future__ import annotations

import hashlib
import json

import pytest

from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay import (
    EVIDENCE_STATE as P85_EVIDENCE_STATE,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay import (
    EVIDENCE_STATE as P87_EVIDENCE_STATE,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding import (
    EVIDENCE_STATE as P88_EVIDENCE_STATE,
    RecoveryStartupReplayStoredIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt import (
    SCHEMA as P89_SCHEMA,
    canonicalize_recovery_startup_replay_retained_identity_binding_receipt,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    replay_recovery_startup_replay_retained_identity_binding_receipt,
)


def _canonical(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _binding(payload: dict[str, object]) -> str:
    return hashlib.sha256(_canonical({
        "sequence": payload["sequence"],
        "lineage_sha256": payload["lineage_sha256"],
        "binding_receipt_payload_sha256": payload["binding_receipt_payload_sha256"],
        "binding_receipt_payload_size_bytes": payload["binding_receipt_payload_size_bytes"],
        "receipt_identity_binding_sha256": payload["receipt_identity_binding_sha256"],
        "retained_identity_payload_sha256": payload["retained_identity_payload_sha256"],
        "retained_identity_payload_size_bytes": payload["retained_identity_payload_size_bytes"],
        "replay_stored_identity_binding_sha256": payload["replay_stored_identity_binding_sha256"],
        "replay_binding_receipt_payload_sha256": payload["replay_binding_receipt_payload_sha256"],
        "replay_binding_receipt_payload_size_bytes": payload["replay_binding_receipt_payload_size_bytes"],
        "retained_replay_identity_payload_sha256": payload["retained_replay_identity_payload_sha256"],
        "retained_replay_identity_payload_size_bytes": payload["retained_replay_identity_payload_size_bytes"],
        "p85_evidence_state": P85_EVIDENCE_STATE,
        "p87_evidence_state": P87_EVIDENCE_STATE,
    })).hexdigest()


def _payload() -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": P89_SCHEMA,
        "sequence": 19,
        "lineage_sha256": "a" * 64,
        "binding_receipt_payload_sha256": "b" * 64,
        "binding_receipt_payload_size_bytes": 101,
        "receipt_identity_binding_sha256": "c" * 64,
        "retained_identity_payload_sha256": "d" * 64,
        "retained_identity_payload_size_bytes": 202,
        "replay_stored_identity_binding_sha256": "e" * 64,
        "replay_binding_receipt_payload_sha256": "f" * 64,
        "replay_binding_receipt_payload_size_bytes": 303,
        "retained_replay_identity_payload_sha256": "1" * 64,
        "retained_replay_identity_payload_size_bytes": 404,
        "replay_retained_identity_binding_sha256": "",
        "p88_evidence_state": P88_EVIDENCE_STATE,
    }
    payload["replay_retained_identity_binding_sha256"] = _binding(payload)
    return payload


def _replay(raw: bytes):
    return replay_recovery_startup_replay_retained_identity_binding_receipt(
        raw,
        expected_payload_sha256=hashlib.sha256(raw).hexdigest(),
        expected_payload_size_bytes=len(raw),
    )


def test_p90_replays_exact_canonical_p89_receipt_and_recomputes_p88_binding() -> None:
    raw = _canonical(_payload())
    evidence = _replay(raw)

    assert evidence.evidence_state == EVIDENCE_STATE
    assert evidence.sequence == 19
    assert evidence.replay_retained_identity_binding_sha256 == _payload()["replay_retained_identity_binding_sha256"]
    assert evidence.replay_retained_identity_binding_receipt_payload_sha256 == hashlib.sha256(raw).hexdigest()
    assert evidence.replay_retained_identity_binding_receipt_payload_size_bytes == len(raw)
    assert evidence.expected_payload_identity_verified is True
    assert evidence.canonical_receipt_verified is True
    assert evidence.dependency_state_verified is True
    assert evidence.replay_retained_identity_binding_recomputed_verified is True
    assert evidence.p88_evidence_state == P88_EVIDENCE_STATE
    assert evidence.automatic_control_allowed is False


def test_p90_accepts_real_p89_encoder_output_end_to_end() -> None:
    payload = _payload()
    p88 = RecoveryStartupReplayStoredIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence(
        sequence=payload["sequence"],
        lineage_sha256=payload["lineage_sha256"],
        binding_receipt_payload_sha256=payload["binding_receipt_payload_sha256"],
        binding_receipt_payload_size_bytes=payload["binding_receipt_payload_size_bytes"],
        receipt_identity_binding_sha256=payload["receipt_identity_binding_sha256"],
        retained_identity_payload_sha256=payload["retained_identity_payload_sha256"],
        retained_identity_payload_size_bytes=payload["retained_identity_payload_size_bytes"],
        replay_stored_identity_binding_sha256=payload["replay_stored_identity_binding_sha256"],
        replay_binding_receipt_payload_sha256=payload["replay_binding_receipt_payload_sha256"],
        replay_binding_receipt_payload_size_bytes=payload["replay_binding_receipt_payload_size_bytes"],
        retained_replay_identity_payload_sha256=payload["retained_replay_identity_payload_sha256"],
        retained_replay_identity_payload_size_bytes=payload["retained_replay_identity_payload_size_bytes"],
        replay_retained_identity_binding_sha256=payload["replay_retained_identity_binding_sha256"],
        p85_contract_verified=True,
        p87_contract_verified=True,
        cross_evidence_identity_verified=True,
    )
    p89 = canonicalize_recovery_startup_replay_retained_identity_binding_receipt(p88)
    replayed = replay_recovery_startup_replay_retained_identity_binding_receipt(
        p89.payload,
        expected_payload_sha256=p89.payload_sha256,
        expected_payload_size_bytes=p89.payload_size_bytes,
    )

    assert replayed.sequence == p89.sequence
    assert replayed.replay_retained_identity_binding_sha256 == p89.replay_retained_identity_binding_sha256
    assert replayed.replay_retained_identity_binding_receipt_payload_sha256 == p89.payload_sha256
    assert replayed.replay_retained_identity_binding_receipt_payload_size_bytes == p89.payload_size_bytes


@pytest.mark.parametrize("expected_sha,expected_size", [("0" * 64, None), (None, 1)])
def test_p90_rejects_wrong_expected_outer_identity(expected_sha, expected_size) -> None:
    raw = _canonical(_payload())
    with pytest.raises(ValueError, match="mismatch"):
        replay_recovery_startup_replay_retained_identity_binding_receipt(
            raw,
            expected_payload_sha256=expected_sha or hashlib.sha256(raw).hexdigest(),
            expected_payload_size_bytes=expected_size or len(raw),
        )


def test_p90_rejects_noncanonical_schema_and_dependency_state_drift() -> None:
    payload = _payload()
    raw = json.dumps(payload, indent=2, sort_keys=True).encode()
    with pytest.raises(ValueError, match="not strict canonical JSON"):
        _replay(raw)

    for field, value, message in (
        ("schema", "morpheus.recovery.p89.other.v1", "schema identifier"),
        ("p88_evidence_state", "DRIFTED", "P88 evidence state"),
    ):
        changed = _payload()
        changed[field] = value
        with pytest.raises(ValueError, match=message):
            _replay(_canonical(changed))


def test_p90_rejects_schema_shape_drift() -> None:
    payload = _payload()
    payload["extra"] = "forbidden"
    with pytest.raises(ValueError, match="schema is incompatible"):
        _replay(_canonical(payload))

    missing = _payload()
    missing.pop("retained_replay_identity_payload_size_bytes")
    with pytest.raises(ValueError, match="schema is incompatible"):
        _replay(_canonical(missing))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sequence", True),
        ("sequence", 0),
        ("lineage_sha256", "A" * 64),
        ("binding_receipt_payload_size_bytes", 0),
        ("receipt_identity_binding_sha256", "x" * 64),
        ("retained_identity_payload_size_bytes", -1),
        ("replay_binding_receipt_payload_size_bytes", True),
        ("retained_replay_identity_payload_size_bytes", 0),
        ("replay_retained_identity_binding_sha256", "2" * 63),
    ],
)
def test_p90_rejects_invalid_serialized_semantic_identities(field, value) -> None:
    payload = _payload()
    payload[field] = value
    with pytest.raises(ValueError):
        _replay(_canonical(payload))


def test_p90_rejects_forged_serialized_p88_binding() -> None:
    payload = _payload()
    payload["replay_retained_identity_binding_sha256"] = "9" * 64
    with pytest.raises(ValueError, match="binding recomputation mismatch"):
        _replay(_canonical(payload))


def test_p90_rejects_semantic_tampering_even_with_fresh_outer_identity() -> None:
    payload = _payload()
    payload["retained_replay_identity_payload_size_bytes"] = 405
    raw = _canonical(payload)
    with pytest.raises(ValueError, match="binding recomputation mismatch"):
        _replay(raw)


def test_p90_rejects_non_bytes_and_malformed_payloads() -> None:
    with pytest.raises(ValueError, match="must be bytes"):
        replay_recovery_startup_replay_retained_identity_binding_receipt(  # type: ignore[arg-type]
            "{}", expected_payload_sha256="0" * 64, expected_payload_size_bytes=2
        )
    for raw, message in ((b"\xff", "valid UTF-8"), (b"{", "valid JSON"), (b"[]", "JSON object")):
        with pytest.raises(ValueError, match=message):
            _replay(raw)


def test_p90_exported_evidence_preserves_read_only_trust_boundary() -> None:
    exported = _replay(_canonical(_payload())).as_dict()
    assert exported["expected_payload_identity_verified"] is True
    assert exported["canonical_receipt_verified"] is True
    assert exported["dependency_state_verified"] is True
    assert exported["replay_retained_identity_binding_recomputed_verified"] is True
    assert exported["automatic_control_allowed"] is False
    assert exported["evidence_state"] == EVIDENCE_STATE
    assert exported["truth_boundary"] == TRUTH_BOUNDARY


def test_p90_truth_boundary_stays_scientifically_and_operationally_narrow() -> None:
    lower = TRUTH_BOUNDARY.lower()
    for phrase in (
        "does not authenticate",
        "freshness",
        "coordinated rollback",
        "authorize startup or mutation",
        "production readiness",
        "benchmark evidence",
        "novelty evidence",
        "automatic-control authority",
    ):
        assert phrase in lower
