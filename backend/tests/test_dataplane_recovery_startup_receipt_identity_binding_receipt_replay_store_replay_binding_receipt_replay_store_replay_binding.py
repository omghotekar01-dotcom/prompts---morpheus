from dataclasses import replace

import pytest

from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay import (
    EVIDENCE_STATE as P85_EVIDENCE_STATE,
    RecoveryStartupReplayStoredIdentityBindingReceiptReplayEvidence,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay import (
    EVIDENCE_STATE as P87_EVIDENCE_STATE,
    RecoveryStartupReplayStoredIdentityBindingReceiptReplayIdentityStoreReplayEvidence,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    bind_recovery_startup_replay_receipt_to_retained_identity_replay,
)

H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64
H4 = "4" * 64
H5 = "5" * 64
H6 = "6" * 64
H7 = "7" * 64
H8 = "8" * 64


def p85(**changes):
    base = RecoveryStartupReplayStoredIdentityBindingReceiptReplayEvidence(
        sequence=11,
        lineage_sha256=H1,
        binding_receipt_payload_sha256=H2,
        binding_receipt_payload_size_bytes=201,
        receipt_identity_binding_sha256=H3,
        retained_identity_payload_sha256=H4,
        retained_identity_payload_size_bytes=302,
        replay_stored_identity_binding_sha256=H5,
        replay_binding_receipt_payload_sha256=H6,
        replay_binding_receipt_payload_size_bytes=403,
        expected_payload_identity_verified=True,
        canonical_receipt_verified=True,
        dependency_state_verified=True,
        replay_stored_identity_binding_recomputed_verified=True,
        p83_evidence_state="carried-p83-state",
    )
    return replace(base, **changes)


def p87(**changes):
    base = RecoveryStartupReplayStoredIdentityBindingReceiptReplayIdentityStoreReplayEvidence(
        sequence=11,
        lineage_sha256=H1,
        binding_receipt_payload_sha256=H2,
        binding_receipt_payload_size_bytes=201,
        receipt_identity_binding_sha256=H3,
        retained_identity_payload_sha256=H4,
        retained_identity_payload_size_bytes=302,
        replay_stored_identity_binding_sha256=H5,
        replay_binding_receipt_payload_sha256=H6,
        replay_binding_receipt_payload_size_bytes=403,
        stored_payload_sha256=H7,
        stored_payload_size_bytes=504,
        source_path="/tmp/p86.json",
        p86_evidence_state_verified=True,
        p86_verification_flags_verified=True,
        exact_payload_identity_verified=True,
        canonical_record_verified=True,
        semantic_agreement_verified=True,
    )
    return replace(base, **changes)


def bind(left=None, right=None):
    return bind_recovery_startup_replay_receipt_to_retained_identity_replay(left or p85(), right or p87())


def test_p88_binds_compatible_p85_and_p87_deterministically():
    first = bind()
    second = bind()
    assert first == second
    assert first.evidence_state == EVIDENCE_STATE
    assert first.automatic_control_allowed is False
    assert first.p85_contract_verified is True
    assert first.p87_contract_verified is True
    assert first.cross_evidence_identity_verified is True
    assert len(first.replay_retained_identity_binding_sha256) == 64


@pytest.mark.parametrize(
    ("left", "right", "match"),
    [
        ({"sequence": 12}, {}, "sequence mismatch"),
        ({"lineage_sha256": H8}, {}, "lineage mismatch"),
        ({"replay_binding_receipt_payload_sha256": H8}, {}, "replay binding receipt SHA-256 mismatch"),
        ({"replay_binding_receipt_payload_size_bytes": 404}, {}, "replay binding receipt byte length mismatch"),
        ({"replay_stored_identity_binding_sha256": H8}, {}, "replay/stored-identity binding mismatch"),
        ({"binding_receipt_payload_sha256": H8}, {}, "binding receipt SHA-256 mismatch"),
        ({"binding_receipt_payload_size_bytes": 202}, {}, "binding receipt byte length mismatch"),
        ({"receipt_identity_binding_sha256": H8}, {}, "receipt identity binding mismatch"),
        ({"retained_identity_payload_sha256": H8}, {}, "retained identity SHA-256 mismatch"),
        ({"retained_identity_payload_size_bytes": 303}, {}, "retained identity byte length mismatch"),
    ],
)
def test_p88_rejects_cross_evidence_identity_disagreement(left, right, match):
    with pytest.raises(ValueError, match=match):
        bind(p85(**left), p87(**right))


@pytest.mark.parametrize(
    "field",
    [
        "expected_payload_identity_verified",
        "canonical_receipt_verified",
        "dependency_state_verified",
        "replay_stored_identity_binding_recomputed_verified",
    ],
)
def test_p88_rejects_weakened_p85_contract(field):
    with pytest.raises(ValueError, match="P85"):
        bind(p85(**{field: False}), p87())


@pytest.mark.parametrize(
    "field",
    [
        "p86_evidence_state_verified",
        "p86_verification_flags_verified",
        "exact_payload_identity_verified",
        "canonical_record_verified",
        "semantic_agreement_verified",
    ],
)
def test_p88_rejects_weakened_p87_contract(field):
    with pytest.raises(ValueError, match="P87"):
        bind(p85(), p87(**{field: False}))


def test_p88_rejects_evidence_state_or_authority_escalation():
    with pytest.raises(ValueError, match="P85.*state"):
        bind(p85(evidence_state="wrong"), p87())
    with pytest.raises(ValueError, match="P87.*state"):
        bind(p85(), p87(evidence_state="wrong"))
    with pytest.raises(ValueError, match="automatic-control"):
        bind(p85(automatic_control_allowed=True), p87())
    with pytest.raises(ValueError, match="automatic-control"):
        bind(p85(), p87(automatic_control_allowed=True))


def test_p88_rejects_boolean_sequence_and_malformed_identity():
    with pytest.raises(ValueError, match="positive integer"):
        bind(p85(sequence=True), p87(sequence=True))
    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        bind(p85(lineage_sha256="A" * 64), p87())


def test_p88_binding_commits_to_selected_retained_p86_record_identity():
    first = bind()
    second = bind(p85(), p87(stored_payload_sha256=H8))
    assert first.replay_retained_identity_binding_sha256 != second.replay_retained_identity_binding_sha256


def test_p88_binding_commits_to_selected_retained_p86_record_size():
    first = bind()
    second = bind(p85(), p87(stored_payload_size_bytes=505))
    assert first.replay_retained_identity_binding_sha256 != second.replay_retained_identity_binding_sha256


def test_p88_binding_commits_to_dependency_evidence_state_contracts(monkeypatch):
    import app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding as module

    first = bind()
    monkeypatch.setattr(module, "P87_EVIDENCE_STATE", "different-contract")
    changed = p87(evidence_state="different-contract")
    second = module.bind_recovery_startup_replay_receipt_to_retained_identity_replay(p85(), changed)
    assert first.replay_retained_identity_binding_sha256 != second.replay_retained_identity_binding_sha256


def test_p88_exported_evidence_and_truth_boundary_remain_non_authoritative():
    evidence = bind()
    exported = evidence.as_dict()
    assert exported["automatic_control_allowed"] is False
    assert exported["truth_boundary"] == TRUTH_BOUNDARY
    boundary = TRUTH_BOUNDARY.lower()
    for phrase in (
        "read-only",
        "freshness",
        "rollback",
        "startup",
        "production readiness",
        "benchmark evidence",
        "novelty evidence",
        "automatic-control authority",
    ):
        assert phrase in boundary


def test_p88_rejects_incompatible_input_types():
    with pytest.raises(ValueError, match="P85"):
        bind_recovery_startup_replay_receipt_to_retained_identity_replay(object(), p87())
    with pytest.raises(ValueError, match="P87"):
        bind_recovery_startup_replay_receipt_to_retained_identity_replay(p85(), object())


def test_p88_evidence_state_contracts_are_exact():
    assert p85().evidence_state == P85_EVIDENCE_STATE
    assert p87().evidence_state == P87_EVIDENCE_STATE
