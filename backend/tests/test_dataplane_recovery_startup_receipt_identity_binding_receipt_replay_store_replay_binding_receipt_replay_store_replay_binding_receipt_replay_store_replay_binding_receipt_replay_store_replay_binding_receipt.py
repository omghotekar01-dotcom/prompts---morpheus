from __future__ import annotations

from dataclasses import replace
import hashlib
import json

import pytest

from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding import (
    EVIDENCE_STATE as P98_EVIDENCE_STATE,
    RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt import (
    EVIDENCE_STATE,
    SCHEMA,
    TRUTH_BOUNDARY,
    canonicalize_recovery_startup_p95_p97_replay_composition_binding_receipt,
)

FIELDS = (
    ("sequence", "int"),
    ("lineage_sha256", "sha"),
    ("binding_receipt_payload_sha256", "sha"),
    ("binding_receipt_payload_size_bytes", "int"),
    ("receipt_identity_binding_sha256", "sha"),
    ("retained_identity_payload_sha256", "sha"),
    ("retained_identity_payload_size_bytes", "int"),
    ("replay_stored_identity_binding_sha256", "sha"),
    ("replay_binding_receipt_payload_sha256", "sha"),
    ("replay_binding_receipt_payload_size_bytes", "int"),
    ("retained_replay_identity_payload_sha256", "sha"),
    ("retained_replay_identity_payload_size_bytes", "int"),
    ("replay_retained_identity_binding_sha256", "sha"),
    ("replay_retained_identity_binding_receipt_payload_sha256", "sha"),
    ("replay_retained_identity_binding_receipt_payload_size_bytes", "int"),
    ("retained_replay_receipt_identity_payload_sha256", "sha"),
    ("retained_replay_receipt_identity_payload_size_bytes", "int"),
    ("replay_retained_receipt_identity_binding_sha256", "sha"),
    ("replay_retained_receipt_identity_binding_receipt_payload_sha256", "sha"),
    ("replay_retained_receipt_identity_binding_receipt_payload_size_bytes", "int"),
    ("retained_replayed_receipt_identity_payload_sha256", "sha"),
    ("retained_replayed_receipt_identity_payload_size_bytes", "int"),
    ("replayed_receipt_retained_identity_binding_sha256", "sha"),
)


def evidence():
    values = {}
    sha_index = 0
    size_value = 101
    for field, kind in FIELDS:
        if kind == "sha":
            sha_index += 1
            values[field] = hashlib.sha256(f"p99-{sha_index}".encode()).hexdigest()
        else:
            values[field] = 7 if field == "sequence" else size_value
            size_value += 1
    return RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence(
        **values,
        p95_contract_verified=True,
        p97_contract_verified=True,
        cross_evidence_identity_verified=True,
    )


def test_p99_is_deterministic_canonical_and_exactly_identified():
    first = canonicalize_recovery_startup_p95_p97_replay_composition_binding_receipt(evidence())
    second = canonicalize_recovery_startup_p95_p97_replay_composition_binding_receipt(evidence())
    assert first.payload == second.payload
    assert first.payload_sha256 == hashlib.sha256(first.payload).hexdigest()
    assert first.payload_size_bytes == len(first.payload)
    document = json.loads(first.payload)
    assert first.payload == json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    assert document["schema"] == SCHEMA
    assert document["p98_evidence_state"] == P98_EVIDENCE_STATE
    assert first.evidence_state == EVIDENCE_STATE
    assert first.p98_contract_verified is True
    assert first.canonical_receipt_verified is True
    assert first.automatic_control_allowed is False


@pytest.mark.parametrize("flag", ["p95_contract_verified", "p97_contract_verified", "cross_evidence_identity_verified"])
def test_p99_rejects_weakened_p98_contract(flag):
    with pytest.raises(ValueError, match="verification flags"):
        canonicalize_recovery_startup_p95_p97_replay_composition_binding_receipt(replace(evidence(), **{flag: False}))


def test_p99_rejects_state_and_control_escalation():
    with pytest.raises(ValueError, match="state is incompatible"):
        canonicalize_recovery_startup_p95_p97_replay_composition_binding_receipt(replace(evidence(), evidence_state="forged"))
    with pytest.raises(ValueError, match="must not grant"):
        canonicalize_recovery_startup_p95_p97_replay_composition_binding_receipt(replace(evidence(), automatic_control_allowed=True))


@pytest.mark.parametrize("value", [True, 0, -1])
def test_p99_rejects_invalid_sequence(value):
    with pytest.raises(ValueError, match="positive integer"):
        canonicalize_recovery_startup_p95_p97_replay_composition_binding_receipt(replace(evidence(), sequence=value))


@pytest.mark.parametrize("field", [field for field, kind in FIELDS if kind == "sha"])
def test_p99_rejects_malformed_hashes(field):
    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        canonicalize_recovery_startup_p95_p97_replay_composition_binding_receipt(replace(evidence(), **{field: "Z" * 64}))


@pytest.mark.parametrize("field", [field for field, kind in FIELDS if kind == "int" and field != "sequence"])
def test_p99_rejects_invalid_sizes(field):
    with pytest.raises(ValueError, match="positive integer"):
        canonicalize_recovery_startup_p95_p97_replay_composition_binding_receipt(replace(evidence(), **{field: True}))


@pytest.mark.parametrize("field,kind", FIELDS)
def test_p99_payload_identity_changes_for_each_semantic_field(field, kind):
    base_evidence = evidence()
    base = canonicalize_recovery_startup_p95_p97_replay_composition_binding_receipt(base_evidence)
    changed_value = 9999 if kind == "int" else hashlib.sha256(f"changed-{field}".encode()).hexdigest()
    changed = canonicalize_recovery_startup_p95_p97_replay_composition_binding_receipt(replace(base_evidence, **{field: changed_value}))
    assert changed.payload != base.payload
    assert changed.payload_sha256 != base.payload_sha256


def test_p99_rejects_incompatible_type():
    with pytest.raises(ValueError, match="incompatible type"):
        canonicalize_recovery_startup_p95_p97_replay_composition_binding_receipt(object())


def test_p99_truth_boundary_remains_read_only_and_non_claiming():
    receipt = canonicalize_recovery_startup_p95_p97_replay_composition_binding_receipt(evidence())
    exported = receipt.as_dict()
    assert exported["truth_boundary"] == TRUTH_BOUNDARY
    boundary = TRUTH_BOUNDARY.lower()
    for phrase in (
        "does not authenticate",
        "freshness",
        "rollback",
        "authorize startup",
        "production readiness",
        "benchmark evidence",
        "novelty evidence",
    ):
        assert phrase in boundary
    assert receipt.automatic_control_allowed is False
