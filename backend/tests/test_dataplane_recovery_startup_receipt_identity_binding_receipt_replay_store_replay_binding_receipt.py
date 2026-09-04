from dataclasses import replace
import hashlib
import json

import pytest

from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding import (
    EVIDENCE_STATE as P83_EVIDENCE_STATE,
    RecoveryStartupStoredReceiptBindingReceiptReplayStoredIdentityBindingEvidence,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt import (
    EVIDENCE_STATE,
    SCHEMA,
    TRUTH_BOUNDARY,
    canonicalize_recovery_startup_replay_stored_identity_binding_receipt,
)


def p83(**changes):
    base = RecoveryStartupStoredReceiptBindingReceiptReplayStoredIdentityBindingEvidence(
        sequence=7,
        lineage_sha256="1" * 64,
        binding_receipt_payload_sha256="2" * 64,
        binding_receipt_payload_size_bytes=311,
        receipt_identity_binding_sha256="3" * 64,
        retained_identity_payload_sha256="4" * 64,
        retained_identity_payload_size_bytes=405,
        replay_stored_identity_binding_sha256="5" * 64,
        p80_contract_verified=True,
        p82_contract_verified=True,
        cross_evidence_identity_verified=True,
    )
    return replace(base, **changes)


def test_p84_emits_deterministic_canonical_receipt_identity():
    first = canonicalize_recovery_startup_replay_stored_identity_binding_receipt(p83())
    second = canonicalize_recovery_startup_replay_stored_identity_binding_receipt(p83())

    assert first.payload == second.payload
    assert first.payload_sha256 == hashlib.sha256(first.payload).hexdigest()
    assert first.payload_size_bytes == len(first.payload)
    assert first.p83_contract_verified is True
    assert first.canonical_receipt_verified is True
    assert first.evidence_state == EVIDENCE_STATE
    assert first.automatic_control_allowed is False

    decoded = json.loads(first.payload)
    assert set(decoded) == {
        "schema",
        "sequence",
        "lineage_sha256",
        "binding_receipt_payload_sha256",
        "binding_receipt_payload_size_bytes",
        "receipt_identity_binding_sha256",
        "retained_identity_payload_sha256",
        "retained_identity_payload_size_bytes",
        "replay_stored_identity_binding_sha256",
        "p83_evidence_state",
    }
    assert decoded["schema"] == SCHEMA
    assert decoded["p83_evidence_state"] == P83_EVIDENCE_STATE
    assert decoded["replay_stored_identity_binding_sha256"] == "5" * 64
    assert first.payload == json.dumps(decoded, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


@pytest.mark.parametrize("field", ["p80_contract_verified", "p82_contract_verified", "cross_evidence_identity_verified"])
def test_p84_rejects_weakened_p83_contract(field):
    with pytest.raises(ValueError, match="verification is incomplete"):
        canonicalize_recovery_startup_replay_stored_identity_binding_receipt(p83(**{field: False}))


def test_p84_rejects_incompatible_state_and_control_escalation():
    with pytest.raises(ValueError, match="state is incompatible"):
        canonicalize_recovery_startup_replay_stored_identity_binding_receipt(p83(evidence_state="OTHER"))
    with pytest.raises(ValueError, match="automatic-control"):
        canonicalize_recovery_startup_replay_stored_identity_binding_receipt(p83(automatic_control_allowed=True))


@pytest.mark.parametrize("sequence", [True, 0, -1, "7"])
def test_p84_rejects_invalid_sequence(sequence):
    with pytest.raises(ValueError, match="positive integer"):
        canonicalize_recovery_startup_replay_stored_identity_binding_receipt(p83(sequence=sequence))


@pytest.mark.parametrize(
    "changes",
    [
        {"lineage_sha256": "A" * 64},
        {"binding_receipt_payload_sha256": "x" * 64},
        {"receipt_identity_binding_sha256": "3" * 63},
        {"retained_identity_payload_sha256": 4},
        {"replay_stored_identity_binding_sha256": "g" * 64},
        {"binding_receipt_payload_size_bytes": False},
        {"retained_identity_payload_size_bytes": 0},
    ],
)
def test_p84_rejects_malformed_identities(changes):
    with pytest.raises(ValueError):
        canonicalize_recovery_startup_replay_stored_identity_binding_receipt(p83(**changes))


@pytest.mark.parametrize(
    "changes",
    [
        {"sequence": 8},
        {"lineage_sha256": "6" * 64},
        {"binding_receipt_payload_sha256": "7" * 64},
        {"binding_receipt_payload_size_bytes": 312},
        {"receipt_identity_binding_sha256": "8" * 64},
        {"retained_identity_payload_sha256": "9" * 64},
        {"retained_identity_payload_size_bytes": 406},
        {"replay_stored_identity_binding_sha256": "a" * 64},
    ],
)
def test_p84_receipt_identity_is_sensitive_to_every_bound_semantic(changes):
    first = canonicalize_recovery_startup_replay_stored_identity_binding_receipt(p83())
    second = canonicalize_recovery_startup_replay_stored_identity_binding_receipt(p83(**changes))
    assert first.payload_sha256 != second.payload_sha256


def test_p84_rejects_non_p83_input():
    with pytest.raises(ValueError, match="incompatible type"):
        canonicalize_recovery_startup_replay_stored_identity_binding_receipt(object())


def test_p84_truth_boundary_is_explicitly_read_only_and_non_authoritative():
    lowered = TRUTH_BOUNDARY.lower()
    assert "read-only" in lowered
    assert "freshness" in lowered
    assert "rollback" in lowered
    assert "startup" in lowered
    assert "production readiness" in lowered
    assert "benchmark evidence" in lowered
    assert "novelty evidence" in lowered
