from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.dataplane_recovery_anchor_observation import (
    RecoveryExpectedHeadPostReleaseObservationEvidence,
)
from app.dataplane_recovery_anchor_ownership import EVIDENCE_STATE as P70_EVIDENCE_STATE
from app.dataplane_recovery_anchor_repeat_observation import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    verify_recovery_expected_head_repeat_observation,
)


def _payload(sequence: int = 7, lineage_sha256: str = "a" * 64) -> bytes:
    return json.dumps(
        {"lineage_sha256": lineage_sha256, "sequence": sequence},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _p71_evidence(anchor, lock, *, sequence: int = 7, lineage_sha256: str = "a" * 64):
    payload = anchor.read_bytes()
    return RecoveryExpectedHeadPostReleaseObservationEvidence(
        sequence=sequence,
        lineage_sha256=lineage_sha256,
        anchor_payload_sha256=hashlib.sha256(payload).hexdigest(),
        anchor_payload_size_bytes=len(payload),
        lock_path=str(lock),
        lock_absent_when_observed=True,
        exact_byte_identity_verified=True,
        canonical_semantics_verified=True,
        p70_evidence_state=P70_EVIDENCE_STATE,
    )


def test_repeat_observation_revalidates_exact_unlocked_anchor(tmp_path):
    anchor = tmp_path / "expected-head.json"
    lock = tmp_path / ".expected-head.lock"
    anchor.write_bytes(_payload())

    evidence = verify_recovery_expected_head_repeat_observation(
        anchor, _p71_evidence(anchor, lock)
    )

    assert evidence.evidence_state == EVIDENCE_STATE
    assert evidence.sequence == 7
    assert evidence.lineage_sha256 == "a" * 64
    assert evidence.lock_absent_before_second_read is True
    assert evidence.lock_absent_after_second_read is True
    assert evidence.exact_second_read_identity_verified is True
    assert evidence.canonical_semantics_reverified is True
    assert evidence.automatic_control_allowed is False
    assert "not CAS" in evidence.as_dict()["truth_boundary"]


def test_repeat_observation_rejects_incompatible_or_weakened_p71_evidence(tmp_path):
    anchor = tmp_path / "expected-head.json"
    lock = tmp_path / ".expected-head.lock"
    anchor.write_bytes(_payload())
    base = _p71_evidence(anchor, lock)

    variants = (
        replace(base, evidence_state="wrong"),
        replace(base, p70_evidence_state="wrong"),
        replace(base, lock_absent_when_observed=False),
        replace(base, exact_byte_identity_verified=False),
        replace(base, canonical_semantics_verified=False),
        replace(base, automatic_control_allowed=True),
    )
    for evidence in variants:
        with pytest.raises(ValueError):
            verify_recovery_expected_head_repeat_observation(anchor, evidence)


def test_repeat_observation_fails_when_lock_is_present(tmp_path):
    anchor = tmp_path / "expected-head.json"
    lock = tmp_path / ".expected-head.lock"
    anchor.write_bytes(_payload())
    evidence = _p71_evidence(anchor, lock)
    lock.write_text("cooperative writer", encoding="utf-8")

    with pytest.raises(RuntimeError, match="lock present"):
        verify_recovery_expected_head_repeat_observation(anchor, evidence)


def test_repeat_observation_detects_anchor_drift_after_p71(tmp_path):
    anchor = tmp_path / "expected-head.json"
    lock = tmp_path / ".expected-head.lock"
    anchor.write_bytes(_payload())
    evidence = _p71_evidence(anchor, lock)
    anchor.write_bytes(_payload(sequence=8, lineage_sha256="b" * 64))

    with pytest.raises(ValueError):
        verify_recovery_expected_head_repeat_observation(anchor, evidence)


def test_repeat_observation_rejects_disappeared_anchor(tmp_path):
    anchor = tmp_path / "expected-head.json"
    lock = tmp_path / ".expected-head.lock"
    anchor.write_bytes(_payload())
    evidence = _p71_evidence(anchor, lock)
    anchor.unlink()

    with pytest.raises(RuntimeError, match="disappeared"):
        verify_recovery_expected_head_repeat_observation(anchor, evidence)


def test_repeat_observation_is_historical_evidence_not_a_lease(tmp_path):
    anchor = tmp_path / "expected-head.json"
    lock = tmp_path / ".expected-head.lock"
    anchor.write_bytes(_payload())
    evidence = verify_recovery_expected_head_repeat_observation(
        anchor, _p71_evidence(anchor, lock)
    )

    anchor.write_bytes(_payload(sequence=8, lineage_sha256="b" * 64))

    assert evidence.sequence == 7
    assert evidence.lineage_sha256 == "a" * 64
    assert "transient mutation" in TRUTH_BOUNDARY
    assert evidence.automatic_control_allowed is False
