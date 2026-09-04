from __future__ import annotations

from dataclasses import replace

import pytest

from app.dataplane_recovery_startup_receipt_identity_binding import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    bind_recovery_startup_receipt_to_stored_identity,
)
from app.dataplane_recovery_startup_receipt_identity_replay import (
    RecoveryStartupReceiptIdentityReplayEvidence,
)
from app.dataplane_recovery_startup_receipt_replay import (
    RecoveryStartupAdmissionReceiptReplayEvidence,
)


def _p75() -> RecoveryStartupAdmissionReceiptReplayEvidence:
    return RecoveryStartupAdmissionReceiptReplayEvidence(
        sequence=7,
        lineage_sha256="a" * 64,
        admission_binding_sha256="b" * 64,
        receipt_payload_sha256="c" * 64,
        receipt_payload_size_bytes=321,
        expected_payload_identity_verified=True,
        canonical_receipt_verified=True,
        admission_binding_recomputed_verified=True,
        dependency_states_verified=True,
    )


def _p77() -> RecoveryStartupReceiptIdentityReplayEvidence:
    return RecoveryStartupReceiptIdentityReplayEvidence(
        sequence=7,
        lineage_sha256="a" * 64,
        receipt_payload_sha256="c" * 64,
        receipt_payload_size_bytes=321,
        admission_binding_sha256="b" * 64,
        stored_payload_sha256="d" * 64,
        stored_payload_size_bytes=256,
        source_path="startup-receipt-head.json",
        expected_payload_identity_verified=True,
        canonical_record_verified=True,
        semantic_identity_verified=True,
    )


def test_p78_binds_matching_p75_and_p77_evidence_deterministically() -> None:
    first = bind_recovery_startup_receipt_to_stored_identity(_p75(), _p77())
    second = bind_recovery_startup_receipt_to_stored_identity(_p75(), _p77())

    assert first == second
    assert first.evidence_state == EVIDENCE_STATE
    assert first.sequence == 7
    assert first.lineage_sha256 == "a" * 64
    assert first.receipt_payload_sha256 == "c" * 64
    assert first.receipt_payload_size_bytes == 321
    assert first.admission_binding_sha256 == "b" * 64
    assert first.stored_identity_payload_sha256 == "d" * 64
    assert first.stored_identity_payload_size_bytes == 256
    assert len(first.receipt_identity_binding_sha256) == 64
    assert first.p75_contract_verified is True
    assert first.p77_contract_verified is True
    assert first.cross_evidence_identity_verified is True
    assert first.automatic_control_allowed is False


@pytest.mark.parametrize(
    ("p75_mutation", "p77_mutation", "message"),
    [
        ({"sequence": 8}, {}, "sequence mismatch"),
        ({}, {"lineage_sha256": "e" * 64}, "lineage mismatch"),
        ({"receipt_payload_sha256": "f" * 64}, {}, "receipt SHA-256 mismatch"),
        ({}, {"receipt_payload_size_bytes": 322}, "receipt byte length mismatch"),
        ({"admission_binding_sha256": "1" * 64}, {}, "binding mismatch"),
    ],
)
def test_p78_rejects_cross_evidence_identity_drift(
    p75_mutation, p77_mutation, message
) -> None:
    with pytest.raises(ValueError, match=message):
        bind_recovery_startup_receipt_to_stored_identity(
            replace(_p75(), **p75_mutation),
            replace(_p77(), **p77_mutation),
        )


@pytest.mark.parametrize(
    "mutation",
    [
        {"evidence_state": "WRONG"},
        {"automatic_control_allowed": True},
        {"expected_payload_identity_verified": False},
        {"canonical_receipt_verified": False},
        {"admission_binding_recomputed_verified": False},
        {"dependency_states_verified": False},
        {"sequence": True},
        {"sequence": 0},
        {"lineage_sha256": "A" * 64},
        {"receipt_payload_sha256": "g" * 64},
        {"receipt_payload_size_bytes": 0},
        {"admission_binding_sha256": "0" * 63},
    ],
)
def test_p78_rejects_incompatible_or_weakened_p75_evidence(mutation) -> None:
    with pytest.raises(ValueError):
        bind_recovery_startup_receipt_to_stored_identity(
            replace(_p75(), **mutation), _p77()
        )


@pytest.mark.parametrize(
    "mutation",
    [
        {"evidence_state": "WRONG"},
        {"automatic_control_allowed": True},
        {"expected_payload_identity_verified": False},
        {"canonical_record_verified": False},
        {"semantic_identity_verified": False},
        {"sequence": True},
        {"sequence": 0},
        {"lineage_sha256": "A" * 64},
        {"receipt_payload_sha256": "g" * 64},
        {"receipt_payload_size_bytes": 0},
        {"admission_binding_sha256": "0" * 63},
        {"stored_payload_sha256": "0" * 63},
        {"stored_payload_size_bytes": 0},
    ],
)
def test_p78_rejects_incompatible_or_weakened_p77_evidence(mutation) -> None:
    with pytest.raises(ValueError):
        bind_recovery_startup_receipt_to_stored_identity(
            _p75(), replace(_p77(), **mutation)
        )


def test_p78_rejects_non_dependency_objects() -> None:
    with pytest.raises(ValueError, match="P75"):
        bind_recovery_startup_receipt_to_stored_identity(
            object(), _p77()  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="P77"):
        bind_recovery_startup_receipt_to_stored_identity(
            _p75(), object()  # type: ignore[arg-type]
        )


def test_p78_binding_changes_when_p77_stored_identity_changes() -> None:
    first = bind_recovery_startup_receipt_to_stored_identity(_p75(), _p77())
    second = bind_recovery_startup_receipt_to_stored_identity(
        _p75(), replace(_p77(), stored_payload_sha256="e" * 64)
    )

    assert first.receipt_identity_binding_sha256 != second.receipt_identity_binding_sha256


def test_p78_is_composition_evidence_not_freshness_or_startup_authority() -> None:
    evidence = bind_recovery_startup_receipt_to_stored_identity(_p75(), _p77())

    assert evidence.automatic_control_allowed is False
    assert "coordinated rollback/replay" in TRUTH_BOUNDARY
    assert "freshness" in TRUTH_BOUNDARY
    assert "authorize startup" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark" in TRUTH_BOUNDARY
    assert "novelty" in TRUTH_BOUNDARY
