from dataclasses import replace

import pytest

from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay import (
    EVIDENCE_STATE as P90_EVIDENCE_STATE,
    RecoveryStartupReplayRetainedIdentityBindingReceiptReplayEvidence,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay import (
    EVIDENCE_STATE as P92_EVIDENCE_STATE,
    RecoveryStartupReplayRetainedIdentityBindingReceiptReplayIdentityStoreReplayEvidence,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    bind_recovery_startup_replay_retained_receipt_to_retained_identity_replay,
)

H = {str(i): f"{i:x}" * 64 for i in range(1, 10)}
H["a"] = "a" * 64
H["b"] = "b" * 64


def p90(**changes):
    base = RecoveryStartupReplayRetainedIdentityBindingReceiptReplayEvidence(
        sequence=17,
        lineage_sha256=H["1"],
        binding_receipt_payload_sha256=H["2"],
        binding_receipt_payload_size_bytes=101,
        receipt_identity_binding_sha256=H["3"],
        retained_identity_payload_sha256=H["4"],
        retained_identity_payload_size_bytes=202,
        replay_stored_identity_binding_sha256=H["5"],
        replay_binding_receipt_payload_sha256=H["6"],
        replay_binding_receipt_payload_size_bytes=303,
        retained_replay_identity_payload_sha256=H["7"],
        retained_replay_identity_payload_size_bytes=404,
        replay_retained_identity_binding_sha256=H["8"],
        replay_retained_identity_binding_receipt_payload_sha256=H["9"],
        replay_retained_identity_binding_receipt_payload_size_bytes=505,
        expected_payload_identity_verified=True,
        canonical_receipt_verified=True,
        dependency_state_verified=True,
        replay_retained_identity_binding_recomputed_verified=True,
        p88_evidence_state="carried-p88-state",
    )
    return replace(base, **changes)


def p92(**changes):
    base = RecoveryStartupReplayRetainedIdentityBindingReceiptReplayIdentityStoreReplayEvidence(
        sequence=17,
        lineage_sha256=H["1"],
        binding_receipt_payload_sha256=H["2"],
        binding_receipt_payload_size_bytes=101,
        receipt_identity_binding_sha256=H["3"],
        retained_identity_payload_sha256=H["4"],
        retained_identity_payload_size_bytes=202,
        replay_stored_identity_binding_sha256=H["5"],
        replay_binding_receipt_payload_sha256=H["6"],
        replay_binding_receipt_payload_size_bytes=303,
        retained_replay_identity_payload_sha256=H["7"],
        retained_replay_identity_payload_size_bytes=404,
        replay_retained_identity_binding_sha256=H["8"],
        replay_retained_identity_binding_receipt_payload_sha256=H["9"],
        replay_retained_identity_binding_receipt_payload_size_bytes=505,
        stored_payload_sha256=H["a"],
        stored_payload_size_bytes=606,
        source_path="/tmp/p91.json",
        p91_evidence_state_verified=True,
        p91_verification_flags_verified=True,
        exact_payload_identity_verified=True,
        canonical_record_verified=True,
        semantic_agreement_verified=True,
    )
    return replace(base, **changes)


def bind(left=None, right=None):
    return bind_recovery_startup_replay_retained_receipt_to_retained_identity_replay(left or p90(), right or p92())


def test_p93_binds_compatible_evidence_deterministically():
    first = bind()
    second = bind()
    assert first == second
    assert first.evidence_state == EVIDENCE_STATE
    assert first.automatic_control_allowed is False
    assert first.p90_contract_verified is True
    assert first.p92_contract_verified is True
    assert first.cross_evidence_identity_verified is True
    assert first.retained_replay_receipt_identity_payload_sha256 == H["a"]
    assert first.retained_replay_receipt_identity_payload_size_bytes == 606
    assert len(first.replay_retained_receipt_identity_binding_sha256) == 64


@pytest.mark.parametrize(
    "field,bad",
    [
        ("sequence", 18),
        ("lineage_sha256", H["b"]),
        ("binding_receipt_payload_sha256", H["b"]),
        ("binding_receipt_payload_size_bytes", 102),
        ("receipt_identity_binding_sha256", H["b"]),
        ("retained_identity_payload_sha256", H["b"]),
        ("retained_identity_payload_size_bytes", 203),
        ("replay_stored_identity_binding_sha256", H["b"]),
        ("replay_binding_receipt_payload_sha256", H["b"]),
        ("replay_binding_receipt_payload_size_bytes", 304),
        ("retained_replay_identity_payload_sha256", H["b"]),
        ("retained_replay_identity_payload_size_bytes", 405),
        ("replay_retained_identity_binding_sha256", H["b"]),
        ("replay_retained_identity_binding_receipt_payload_sha256", H["b"]),
        ("replay_retained_identity_binding_receipt_payload_size_bytes", 506),
    ],
)
def test_p93_rejects_cross_evidence_identity_mismatch(field, bad):
    with pytest.raises(ValueError, match="P90/P92"):
        bind(right=p92(**{field: bad}))


@pytest.mark.parametrize(
    "field",
    [
        "expected_payload_identity_verified",
        "canonical_receipt_verified",
        "dependency_state_verified",
        "replay_retained_identity_binding_recomputed_verified",
    ],
)
def test_p93_rejects_weakened_p90_contract(field):
    with pytest.raises(ValueError, match="P90 verification flags"):
        bind(left=p90(**{field: False}))


@pytest.mark.parametrize(
    "field",
    [
        "p91_evidence_state_verified",
        "p91_verification_flags_verified",
        "exact_payload_identity_verified",
        "canonical_record_verified",
        "semantic_agreement_verified",
    ],
)
def test_p93_rejects_weakened_p92_contract(field):
    with pytest.raises(ValueError, match="P92 verification flags"):
        bind(right=p92(**{field: False}))


def test_p93_rejects_dependency_state_drift_and_control_escalation():
    with pytest.raises(ValueError, match="P90 evidence state"):
        bind(left=p90(evidence_state="drift"))
    with pytest.raises(ValueError, match="P92 evidence state"):
        bind(right=p92(evidence_state="drift"))
    with pytest.raises(ValueError, match="P90 evidence must not grant"):
        bind(left=p90(automatic_control_allowed=True))
    with pytest.raises(ValueError, match="P92 evidence must not grant"):
        bind(right=p92(automatic_control_allowed=True))


@pytest.mark.parametrize("bad", [True, 0, -1])
def test_p93_rejects_invalid_sequence(bad):
    with pytest.raises(ValueError, match="positive integer"):
        bind(left=p90(sequence=bad), right=p92(sequence=bad))


def test_p93_rejects_malformed_hashes_even_when_both_inputs_match():
    malformed = "A" * 64
    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        bind(left=p90(lineage_sha256=malformed), right=p92(lineage_sha256=malformed))


def test_p93_binding_is_sensitive_to_retained_p91_record_identity():
    first = bind()
    changed_sha = bind(right=p92(stored_payload_sha256=H["b"]))
    changed_size = bind(right=p92(stored_payload_size_bytes=607))
    assert first.replay_retained_receipt_identity_binding_sha256 != changed_sha.replay_retained_receipt_identity_binding_sha256
    assert first.replay_retained_receipt_identity_binding_sha256 != changed_size.replay_retained_receipt_identity_binding_sha256


def test_p93_binding_is_coupled_to_dependency_evidence_states(monkeypatch):
    import app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding as module

    first = bind()
    monkeypatch.setattr(module, "P92_EVIDENCE_STATE", "different-p92-state")
    stored = p92(evidence_state="different-p92-state")
    changed = bind(right=stored)
    assert first.replay_retained_receipt_identity_binding_sha256 != changed.replay_retained_receipt_identity_binding_sha256


def test_p93_rejects_incompatible_types():
    with pytest.raises(ValueError, match="P90"):
        bind_recovery_startup_replay_retained_receipt_to_retained_identity_replay(object(), p92())
    with pytest.raises(ValueError, match="P92"):
        bind_recovery_startup_replay_retained_receipt_to_retained_identity_replay(p90(), object())


def test_p93_truth_boundary_is_explicit_and_non_authoritative():
    text = TRUTH_BOUNDARY.lower()
    assert "read-only" in text
    assert "freshness" in text
    assert "rollback" in text
    assert "startup" in text
    assert "mutation" in text
    assert "production readiness" in text
    assert "benchmark evidence" in text
    assert "novelty evidence" in text
    assert "automatic-control authority" in text
