from dataclasses import replace
import hashlib
import json

import pytest

from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding import (
    EVIDENCE_STATE as P93_EVIDENCE_STATE,
    RecoveryStartupReplayRetainedIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt import (
    EVIDENCE_STATE,
    SCHEMA,
    TRUTH_BOUNDARY,
    canonicalize_recovery_startup_replay_retained_receipt_identity_binding_receipt,
)

H = "a" * 64


def evidence():
    return RecoveryStartupReplayRetainedIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence(
        sequence=7,
        lineage_sha256="1" * 64,
        binding_receipt_payload_sha256="2" * 64,
        binding_receipt_payload_size_bytes=101,
        receipt_identity_binding_sha256="3" * 64,
        retained_identity_payload_sha256="4" * 64,
        retained_identity_payload_size_bytes=102,
        replay_stored_identity_binding_sha256="5" * 64,
        replay_binding_receipt_payload_sha256="6" * 64,
        replay_binding_receipt_payload_size_bytes=103,
        retained_replay_identity_payload_sha256="7" * 64,
        retained_replay_identity_payload_size_bytes=104,
        replay_retained_identity_binding_sha256="8" * 64,
        replay_retained_identity_binding_receipt_payload_sha256="9" * 64,
        replay_retained_identity_binding_receipt_payload_size_bytes=105,
        retained_replay_receipt_identity_payload_sha256="a" * 64,
        retained_replay_receipt_identity_payload_size_bytes=106,
        replay_retained_receipt_identity_binding_sha256="b" * 64,
        p90_contract_verified=True,
        p92_contract_verified=True,
        cross_evidence_identity_verified=True,
    )


def test_p94_is_deterministic_canonical_and_exactly_identified():
    first = canonicalize_recovery_startup_replay_retained_receipt_identity_binding_receipt(evidence())
    second = canonicalize_recovery_startup_replay_retained_receipt_identity_binding_receipt(evidence())
    assert first.payload == second.payload
    assert first.payload_sha256 == hashlib.sha256(first.payload).hexdigest()
    assert first.payload_size_bytes == len(first.payload)
    document = json.loads(first.payload)
    assert first.payload == json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    assert document["schema"] == SCHEMA
    assert document["p93_evidence_state"] == P93_EVIDENCE_STATE
    assert first.evidence_state == EVIDENCE_STATE
    assert first.p93_contract_verified is True
    assert first.canonical_receipt_verified is True
    assert first.automatic_control_allowed is False


@pytest.mark.parametrize("flag", ["p90_contract_verified", "p92_contract_verified", "cross_evidence_identity_verified"])
def test_p94_rejects_weakened_p93_contract(flag):
    with pytest.raises(ValueError, match="verification flags"):
        canonicalize_recovery_startup_replay_retained_receipt_identity_binding_receipt(replace(evidence(), **{flag: False}))


def test_p94_rejects_state_and_control_escalation():
    with pytest.raises(ValueError, match="state is incompatible"):
        canonicalize_recovery_startup_replay_retained_receipt_identity_binding_receipt(replace(evidence(), evidence_state="forged"))
    with pytest.raises(ValueError, match="must not grant"):
        canonicalize_recovery_startup_replay_retained_receipt_identity_binding_receipt(replace(evidence(), automatic_control_allowed=True))


@pytest.mark.parametrize("value", [True, 0, -1])
def test_p94_rejects_invalid_sequence(value):
    with pytest.raises(ValueError, match="positive integer"):
        canonicalize_recovery_startup_replay_retained_receipt_identity_binding_receipt(replace(evidence(), sequence=value))


@pytest.mark.parametrize("field", [
    "lineage_sha256",
    "binding_receipt_payload_sha256",
    "receipt_identity_binding_sha256",
    "retained_identity_payload_sha256",
    "replay_stored_identity_binding_sha256",
    "replay_binding_receipt_payload_sha256",
    "retained_replay_identity_payload_sha256",
    "replay_retained_identity_binding_sha256",
    "replay_retained_identity_binding_receipt_payload_sha256",
    "retained_replay_receipt_identity_payload_sha256",
    "replay_retained_receipt_identity_binding_sha256",
])
def test_p94_rejects_malformed_hashes(field):
    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        canonicalize_recovery_startup_replay_retained_receipt_identity_binding_receipt(replace(evidence(), **{field: "Z" * 64}))


@pytest.mark.parametrize("field", [
    "binding_receipt_payload_size_bytes",
    "retained_identity_payload_size_bytes",
    "replay_binding_receipt_payload_size_bytes",
    "retained_replay_identity_payload_size_bytes",
    "replay_retained_identity_binding_receipt_payload_size_bytes",
    "retained_replay_receipt_identity_payload_size_bytes",
])
def test_p94_rejects_invalid_sizes(field):
    with pytest.raises(ValueError, match="positive integer"):
        canonicalize_recovery_startup_replay_retained_receipt_identity_binding_receipt(replace(evidence(), **{field: True}))


def test_p94_payload_identity_changes_for_semantic_identity_change():
    base = canonicalize_recovery_startup_replay_retained_receipt_identity_binding_receipt(evidence())
    changed = canonicalize_recovery_startup_replay_retained_receipt_identity_binding_receipt(
        replace(evidence(), retained_replay_receipt_identity_payload_size_bytes=999)
    )
    assert changed.payload != base.payload
    assert changed.payload_sha256 != base.payload_sha256


def test_p94_rejects_incompatible_type():
    with pytest.raises(ValueError, match="incompatible type"):
        canonicalize_recovery_startup_replay_retained_receipt_identity_binding_receipt(object())


def test_p94_truth_boundary_remains_read_only_and_non_claiming():
    receipt = canonicalize_recovery_startup_replay_retained_receipt_identity_binding_receipt(evidence())
    exported = receipt.as_dict()
    assert exported["truth_boundary"] == TRUTH_BOUNDARY
    boundary = TRUTH_BOUNDARY.lower()
    for phrase in ("does not authenticate", "freshness", "rollback", "authorize startup", "production readiness", "benchmark evidence", "novelty evidence"):
        assert phrase in boundary
    assert receipt.automatic_control_allowed is False
