from dataclasses import replace

import pytest

from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay import (
    EVIDENCE_STATE as P80_EVIDENCE_STATE,
    RecoveryStartupStoredReceiptBindingReceiptReplayEvidence,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay import (
    EVIDENCE_STATE as P82_EVIDENCE_STATE,
    RecoveryStartupStoredReceiptBindingReceiptReplayIdentityReplayEvidence,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    bind_recovery_startup_binding_receipt_replay_to_stored_identity_replay,
)

H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64
H4 = "4" * 64
H5 = "5" * 64
H6 = "6" * 64
H7 = "7" * 64


def p80(**changes):
    base = RecoveryStartupStoredReceiptBindingReceiptReplayEvidence(
        sequence=9,
        lineage_sha256=H1,
        receipt_payload_sha256=H2,
        receipt_payload_size_bytes=101,
        admission_binding_sha256=H3,
        stored_identity_payload_sha256=H4,
        stored_identity_payload_size_bytes=202,
        receipt_identity_binding_sha256=H5,
        binding_receipt_payload_sha256=H6,
        binding_receipt_payload_size_bytes=303,
        expected_payload_identity_verified=True,
        canonical_receipt_verified=True,
        dependency_state_verified=True,
        receipt_identity_binding_recomputed_verified=True,
        p78_evidence_state="unused-by-p83-but-validly-carried",
    )
    return replace(base, **changes)


def p82(**changes):
    base = RecoveryStartupStoredReceiptBindingReceiptReplayIdentityReplayEvidence(
        sequence=9,
        lineage_sha256=H1,
        binding_receipt_payload_sha256=H6,
        binding_receipt_payload_size_bytes=303,
        receipt_identity_binding_sha256=H5,
        stored_payload_sha256=H7,
        stored_payload_size_bytes=404,
        source_path="/tmp/p81.json",
        expected_payload_identity_verified=True,
        canonical_record_verified=True,
        p80_evidence_state_verified=True,
        semantic_identity_verified=True,
    )
    return replace(base, **changes)


def test_p83_binds_compatible_p80_and_p82_deterministically():
    first = bind_recovery_startup_binding_receipt_replay_to_stored_identity_replay(p80(), p82())
    second = bind_recovery_startup_binding_receipt_replay_to_stored_identity_replay(p80(), p82())
    assert first == second
    assert first.evidence_state == EVIDENCE_STATE
    assert first.automatic_control_allowed is False
    assert first.p80_contract_verified is True
    assert first.p82_contract_verified is True
    assert first.cross_evidence_identity_verified is True
    assert len(first.replay_stored_identity_binding_sha256) == 64


@pytest.mark.parametrize(
    ("left", "right", "match"),
    [
        ({"sequence": 10}, {}, "sequence mismatch"),
        ({"lineage_sha256": H2}, {}, "lineage mismatch"),
        ({"binding_receipt_payload_sha256": H2}, {}, "SHA-256 mismatch"),
        ({"binding_receipt_payload_size_bytes": 304}, {}, "byte length mismatch"),
        ({"receipt_identity_binding_sha256": H2}, {}, "identity binding mismatch"),
    ],
)
def test_p83_rejects_cross_evidence_identity_disagreement(left, right, match):
    with pytest.raises(ValueError, match=match):
        bind_recovery_startup_binding_receipt_replay_to_stored_identity_replay(p80(**left), p82(**right))


@pytest.mark.parametrize(
    "field",
    [
        "expected_payload_identity_verified",
        "canonical_receipt_verified",
        "dependency_state_verified",
        "receipt_identity_binding_recomputed_verified",
    ],
)
def test_p83_rejects_weakened_p80_contract(field):
    with pytest.raises(ValueError, match="P80"):
        bind_recovery_startup_binding_receipt_replay_to_stored_identity_replay(p80(**{field: False}), p82())


@pytest.mark.parametrize(
    "field",
    [
        "expected_payload_identity_verified",
        "canonical_record_verified",
        "p80_evidence_state_verified",
        "semantic_identity_verified",
    ],
)
def test_p83_rejects_weakened_p82_contract(field):
    with pytest.raises(ValueError, match="P82"):
        bind_recovery_startup_binding_receipt_replay_to_stored_identity_replay(p80(), p82(**{field: False}))


def test_p83_rejects_evidence_state_or_authority_escalation():
    with pytest.raises(ValueError, match="P80.*state"):
        bind_recovery_startup_binding_receipt_replay_to_stored_identity_replay(p80(evidence_state="wrong"), p82())
    with pytest.raises(ValueError, match="P82.*state"):
        bind_recovery_startup_binding_receipt_replay_to_stored_identity_replay(p80(), p82(evidence_state="wrong"))
    with pytest.raises(ValueError, match="automatic-control"):
        bind_recovery_startup_binding_receipt_replay_to_stored_identity_replay(p80(automatic_control_allowed=True), p82())
    with pytest.raises(ValueError, match="automatic-control"):
        bind_recovery_startup_binding_receipt_replay_to_stored_identity_replay(p80(), p82(automatic_control_allowed=True))


def test_p83_rejects_boolean_sequence_and_malformed_identity():
    with pytest.raises(ValueError, match="positive integer"):
        bind_recovery_startup_binding_receipt_replay_to_stored_identity_replay(p80(sequence=True), p82(sequence=True))
    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        bind_recovery_startup_binding_receipt_replay_to_stored_identity_replay(p80(lineage_sha256="A" * 64), p82())


@pytest.mark.parametrize(
    "changes",
    [
        {"stored_payload_sha256": "8" * 64},
        {"stored_payload_size_bytes": 405},
    ],
)
def test_p83_binding_is_sensitive_to_retained_identity_payload(changes):
    first = bind_recovery_startup_binding_receipt_replay_to_stored_identity_replay(p80(), p82())
    second = bind_recovery_startup_binding_receipt_replay_to_stored_identity_replay(p80(), p82(**changes))
    assert first.replay_stored_identity_binding_sha256 != second.replay_stored_identity_binding_sha256


def test_p83_truth_boundary_remains_scientific_and_non_authoritative():
    lower = TRUTH_BOUNDARY.lower()
    for phrase in (
        "read-only", "freshness", "rollback", "startup", "production readiness",
        "benchmark evidence", "novelty evidence", "automatic-control authority",
    ):
        assert phrase in lower
    evidence = bind_recovery_startup_binding_receipt_replay_to_stored_identity_replay(p80(), p82())
    assert evidence.automatic_control_allowed is False
    assert evidence.as_dict()["truth_boundary"] == TRUTH_BOUNDARY


def test_p83_is_bound_to_exported_dependency_states():
    assert p80().evidence_state == P80_EVIDENCE_STATE
    assert p82().evidence_state == P82_EVIDENCE_STATE
