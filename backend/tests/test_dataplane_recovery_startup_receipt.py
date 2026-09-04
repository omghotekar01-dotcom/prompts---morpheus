from __future__ import annotations

from dataclasses import replace
import hashlib
import json

import pytest

from app.dataplane_recovery_startup_admission import (
    EVIDENCE_STATE as P73_EVIDENCE_STATE,
    RecoveryStartupAdmissionEvidence,
)
from app.dataplane_recovery_startup_receipt import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    encode_recovery_startup_admission_receipt,
)


def _p73() -> RecoveryStartupAdmissionEvidence:
    return RecoveryStartupAdmissionEvidence(
        sequence=2,
        lineage_sha256="a" * 64,
        p67_binding_sha256="b" * 64,
        observed_anchor_payload_sha256="c" * 64,
        observed_anchor_payload_size_bytes=96,
        admission_binding_sha256="d" * 64,
        recovery_identity_match_verified=True,
        repeated_anchor_identity_bound=True,
        p67_evidence_state="LOCAL_DATA_PLANE_RECOVERY_STORED_EXPECTED_HEAD_CONSISTENCY_VERIFIED",
        p72_evidence_state="LOCAL_DATA_PLANE_RECOVERY_EXPECTED_HEAD_REPEAT_OBSERVATION_VERIFIED",
        evidence_state=P73_EVIDENCE_STATE,
        automatic_control_allowed=False,
    )


def test_p74_emits_deterministic_canonical_startup_admission_receipt() -> None:
    evidence = encode_recovery_startup_admission_receipt(_p73())
    repeated = encode_recovery_startup_admission_receipt(_p73())

    assert evidence == repeated
    assert evidence.evidence_state == EVIDENCE_STATE
    assert evidence.sequence == 2
    assert evidence.lineage_sha256 == "a" * 64
    assert evidence.admission_binding_sha256 == "d" * 64
    assert evidence.canonical_receipt_verified is True
    assert evidence.exact_payload_identity_verified is True
    assert evidence.automatic_control_allowed is False
    assert evidence.receipt_payload_size_bytes == len(evidence.receipt_payload_utf8)
    assert evidence.receipt_payload_sha256 == hashlib.sha256(evidence.receipt_payload_utf8).hexdigest()
    parsed = json.loads(evidence.receipt_payload_utf8.decode("utf-8"))
    assert parsed["sequence"] == 2
    assert parsed["admission_binding_sha256"] == "d" * 64
    assert evidence.receipt_payload_utf8 == json.dumps(
        parsed, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    assert evidence.as_dict()["truth_boundary"] == TRUTH_BOUNDARY


def test_p74_receipt_identity_changes_with_bound_p73_identity() -> None:
    baseline = encode_recovery_startup_admission_receipt(_p73())
    changed = encode_recovery_startup_admission_receipt(
        replace(_p73(), admission_binding_sha256="e" * 64)
    )
    assert changed.receipt_payload_sha256 != baseline.receipt_payload_sha256
    assert changed.receipt_payload_utf8 != baseline.receipt_payload_utf8


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_state", "WRONG"),
        ("recovery_identity_match_verified", False),
        ("repeated_anchor_identity_bound", False),
        ("automatic_control_allowed", True),
        ("sequence", True),
        ("lineage_sha256", "A" * 64),
        ("p67_binding_sha256", "0" * 63),
        ("observed_anchor_payload_sha256", "x" * 64),
        ("observed_anchor_payload_size_bytes", 0),
        ("admission_binding_sha256", "D" * 64),
        ("p67_evidence_state", ""),
        ("p72_evidence_state", ""),
    ],
)
def test_p74_rejects_incompatible_or_weakened_p73(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        encode_recovery_startup_admission_receipt(replace(_p73(), **{field: value}))


def test_p74_is_portability_evidence_not_startup_or_persistence_authority() -> None:
    evidence = encode_recovery_startup_admission_receipt(_p73())

    assert evidence.automatic_control_allowed is False
    assert "does not rerun P73" in TRUTH_BOUNDARY
    assert "persist" in TRUTH_BOUNDARY
    assert "authorize startup" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark evidence" in TRUTH_BOUNDARY
