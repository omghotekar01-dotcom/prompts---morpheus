import hashlib
import json
from dataclasses import replace

import pytest

from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding import (
    EVIDENCE_STATE as P88_EVIDENCE_STATE,
    RecoveryStartupReplayStoredIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt import (
    EVIDENCE_STATE,
    SCHEMA,
    TRUTH_BOUNDARY,
    canonicalize_recovery_startup_replay_retained_identity_binding_receipt,
)


def h(ch: str) -> str:
    return ch * 64


def p88(**overrides):
    base = RecoveryStartupReplayStoredIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence(
        sequence=17,
        lineage_sha256=h("a"),
        binding_receipt_payload_sha256=h("b"),
        binding_receipt_payload_size_bytes=101,
        receipt_identity_binding_sha256=h("c"),
        retained_identity_payload_sha256=h("d"),
        retained_identity_payload_size_bytes=202,
        replay_stored_identity_binding_sha256=h("e"),
        replay_binding_receipt_payload_sha256=h("f"),
        replay_binding_receipt_payload_size_bytes=303,
        retained_replay_identity_payload_sha256=h("1"),
        retained_replay_identity_payload_size_bytes=404,
        replay_retained_identity_binding_sha256=h("2"),
        p85_contract_verified=True,
        p87_contract_verified=True,
        cross_evidence_identity_verified=True,
    )
    return replace(base, **overrides)


def test_p89_emits_deterministic_canonical_receipt_bytes():
    first = canonicalize_recovery_startup_replay_retained_identity_binding_receipt(p88())
    second = canonicalize_recovery_startup_replay_retained_identity_binding_receipt(p88())

    assert first.payload == second.payload
    assert first.payload_sha256 == hashlib.sha256(first.payload).hexdigest()
    assert first.payload_size_bytes == len(first.payload)
    document = json.loads(first.payload.decode("utf-8"))
    assert first.payload == json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    assert document["schema"] == SCHEMA
    assert document["p88_evidence_state"] == P88_EVIDENCE_STATE
    assert first.evidence_state == EVIDENCE_STATE
    assert first.p88_contract_verified is True
    assert first.canonical_receipt_verified is True
    assert first.automatic_control_allowed is False


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
def test_p89_rejects_invalid_semantic_identities(field, value):
    with pytest.raises(ValueError):
        canonicalize_recovery_startup_replay_retained_identity_binding_receipt(p88(**{field: value}))


@pytest.mark.parametrize(
    "field",
    ["p85_contract_verified", "p87_contract_verified", "cross_evidence_identity_verified"],
)
def test_p89_rejects_weakened_p88_verification_contract(field):
    with pytest.raises(ValueError, match="verification is incomplete"):
        canonicalize_recovery_startup_replay_retained_identity_binding_receipt(p88(**{field: False}))


def test_p89_rejects_incompatible_p88_state_and_control_escalation():
    with pytest.raises(ValueError, match="state is incompatible"):
        canonicalize_recovery_startup_replay_retained_identity_binding_receipt(p88(evidence_state="DRIFTED"))
    with pytest.raises(ValueError, match="automatic-control authority"):
        canonicalize_recovery_startup_replay_retained_identity_binding_receipt(p88(automatic_control_allowed=True))


def test_p89_rejects_incompatible_input_type():
    with pytest.raises(ValueError, match="incompatible type"):
        canonicalize_recovery_startup_replay_retained_identity_binding_receipt(object())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sequence", 18),
        ("lineage_sha256", h("3")),
        ("binding_receipt_payload_sha256", h("4")),
        ("binding_receipt_payload_size_bytes", 102),
        ("receipt_identity_binding_sha256", h("5")),
        ("retained_identity_payload_sha256", h("6")),
        ("retained_identity_payload_size_bytes", 203),
        ("replay_stored_identity_binding_sha256", h("7")),
        ("replay_binding_receipt_payload_sha256", h("8")),
        ("replay_binding_receipt_payload_size_bytes", 304),
        ("retained_replay_identity_payload_sha256", h("9")),
        ("retained_replay_identity_payload_size_bytes", 405),
        ("replay_retained_identity_binding_sha256", h("a")),
    ],
)
def test_p89_receipt_identity_is_sensitive_to_every_serialized_semantic_field(field, value):
    first = canonicalize_recovery_startup_replay_retained_identity_binding_receipt(p88())
    second = canonicalize_recovery_startup_replay_retained_identity_binding_receipt(p88(**{field: value}))
    assert first.payload != second.payload
    assert first.payload_sha256 != second.payload_sha256


def test_p89_schema_is_exact_and_contains_no_authority_fields():
    receipt = canonicalize_recovery_startup_replay_retained_identity_binding_receipt(p88())
    document = json.loads(receipt.payload)
    assert set(document) == {
        "schema",
        "sequence",
        "lineage_sha256",
        "binding_receipt_payload_sha256",
        "binding_receipt_payload_size_bytes",
        "receipt_identity_binding_sha256",
        "retained_identity_payload_sha256",
        "retained_identity_payload_size_bytes",
        "replay_stored_identity_binding_sha256",
        "replay_binding_receipt_payload_sha256",
        "replay_binding_receipt_payload_size_bytes",
        "retained_replay_identity_payload_sha256",
        "retained_replay_identity_payload_size_bytes",
        "replay_retained_identity_binding_sha256",
        "p88_evidence_state",
    }
    assert not any("authorize" in key or "control" in key or "fresh" in key for key in document)


def test_p89_truth_boundary_stays_scientifically_and_operationally_narrow():
    lower = TRUTH_BOUNDARY.lower()
    for phrase in (
        "read-only",
        "does not authenticate",
        "freshness",
        "rollback",
        "authorize startup",
        "production readiness",
        "benchmark evidence",
        "novelty evidence",
        "automatic-control authority",
    ):
        assert phrase in lower
