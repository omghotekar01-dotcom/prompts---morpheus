from __future__ import annotations

from dataclasses import replace

import pytest

from app.dataplane_recovery_anchor_rebootstrap import (
    EVIDENCE_STATE as P67_EVIDENCE_STATE,
    RecoveryStoredExpectedHeadEvidence,
)
from app.dataplane_recovery_anchor_repeat_observation import (
    EVIDENCE_STATE as P72_EVIDENCE_STATE,
    RecoveryExpectedHeadRepeatObservationEvidence,
)
from app.dataplane_recovery_startup_admission import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    verify_recovery_startup_admission,
)


def _p67(*, sequence: int = 2, lineage: str = "a" * 64):
    return RecoveryStoredExpectedHeadEvidence(
        sequence=sequence,
        lineage_sha256=lineage,
        predecessor_sequence=sequence - 1,
        predecessor_lineage_sha256="b" * 64,
        anchor_payload_sha256="c" * 64,
        anchor_payload_size_bytes=96,
        binding_sha256="d" * 64,
        stored_anchor_identity_verified=True,
        predecessor_anchor_match_verified=True,
        exact_p65_recomputation_verified=True,
        stored_head_recovery_consistency_verified=True,
        p66_evidence_state="LOCAL_DATA_PLANE_RECOVERY_EXPECTED_HEAD_STORE_VERIFIED",
        p65_evidence_state="LOCAL_DATA_PLANE_RECOVERY_EXPECTED_HEAD_CONSISTENCY_VERIFIED",
        evidence_state=P67_EVIDENCE_STATE,
        automatic_control_allowed=False,
    )


def _p72(*, sequence: int = 2, lineage: str = "a" * 64):
    return RecoveryExpectedHeadRepeatObservationEvidence(
        sequence=sequence,
        lineage_sha256=lineage,
        anchor_payload_sha256="e" * 64,
        anchor_payload_size_bytes=96,
        lock_path="/tmp/morpheus-recovery.lock",
        lock_absent_before_second_read=True,
        lock_absent_after_second_read=True,
        exact_second_read_identity_verified=True,
        canonical_semantics_reverified=True,
        p71_evidence_state="LOCAL_DATA_PLANE_RECOVERY_EXPECTED_HEAD_POST_RELEASE_OBSERVATION_VERIFIED",
        evidence_state=P72_EVIDENCE_STATE,
        automatic_control_allowed=False,
    )


def test_p73_binds_same_current_recovery_and_repeated_anchor_identity() -> None:
    evidence = verify_recovery_startup_admission(_p67(), _p72())

    assert evidence.evidence_state == EVIDENCE_STATE
    assert evidence.sequence == 2
    assert evidence.lineage_sha256 == "a" * 64
    assert evidence.p67_binding_sha256 == "d" * 64
    assert evidence.observed_anchor_payload_sha256 == "e" * 64
    assert evidence.observed_anchor_payload_size_bytes == 96
    assert evidence.recovery_identity_match_verified is True
    assert evidence.repeated_anchor_identity_bound is True
    assert evidence.automatic_control_allowed is False
    assert len(evidence.admission_binding_sha256) == 64
    assert evidence.as_dict()["truth_boundary"] == TRUTH_BOUNDARY

    repeated = verify_recovery_startup_admission(_p67(), _p72())
    assert repeated == evidence


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_state", "WRONG"),
        ("stored_anchor_identity_verified", False),
        ("predecessor_anchor_match_verified", False),
        ("exact_p65_recomputation_verified", False),
        ("stored_head_recovery_consistency_verified", False),
        ("automatic_control_allowed", True),
        ("sequence", True),
        ("lineage_sha256", "A" * 64),
        ("binding_sha256", "0" * 63),
    ],
)
def test_p73_rejects_incompatible_or_weakened_p67(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        verify_recovery_startup_admission(replace(_p67(), **{field: value}), _p72())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_state", "WRONG"),
        ("lock_absent_before_second_read", False),
        ("lock_absent_after_second_read", False),
        ("exact_second_read_identity_verified", False),
        ("canonical_semantics_reverified", False),
        ("automatic_control_allowed", True),
        ("sequence", True),
        ("lineage_sha256", "A" * 64),
        ("anchor_payload_sha256", "0" * 63),
        ("anchor_payload_size_bytes", 0),
    ],
)
def test_p73_rejects_incompatible_or_weakened_p72(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        verify_recovery_startup_admission(_p67(), replace(_p72(), **{field: value}))


def test_p73_rejects_sequence_or_lineage_disagreement() -> None:
    with pytest.raises(ValueError, match="does not match"):
        verify_recovery_startup_admission(_p67(), _p72(sequence=3))
    with pytest.raises(ValueError, match="does not match"):
        verify_recovery_startup_admission(_p67(), _p72(lineage="f" * 64))


def test_p73_is_read_only_evidence_not_startup_authority() -> None:
    evidence = verify_recovery_startup_admission(_p67(), _p72())

    assert evidence.automatic_control_allowed is False
    assert "does not rerun either dependency" in TRUTH_BOUNDARY
    assert "authorize startup" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark evidence" in TRUTH_BOUNDARY
