from __future__ import annotations

import pytest

from app.generated_migration_campaign_revocation import revoke_generated_migration_campaign


def test_revocation_hash_is_order_independent() -> None:
    a = revoke_generated_migration_campaign(
        campaign_decision_sha256="1" * 64,
        reason="report_tampering_detected",
        evidence_sha256=["2" * 64, "3" * 64],
    )
    b = revoke_generated_migration_campaign(
        campaign_decision_sha256="1" * 64,
        reason="report_tampering_detected",
        evidence_sha256=["3" * 64, "2" * 64],
    )
    assert a.revocation_sha256 == b.revocation_sha256
    assert a.evidence_sha256 == ("2" * 64, "3" * 64)


def test_revocation_chain_binds_predecessor() -> None:
    first = revoke_generated_migration_campaign(
        campaign_decision_sha256="1" * 64,
        reason="benchmark_source_retracted",
        evidence_sha256=["2" * 64],
    )
    second = revoke_generated_migration_campaign(
        campaign_decision_sha256="1" * 64,
        reason="measurement_protocol_violation",
        evidence_sha256=["3" * 64],
        predecessor_revocation_sha256=first.revocation_sha256,
    )
    assert second.predecessor_revocation_sha256 == first.revocation_sha256
    assert second.revocation_sha256 != first.revocation_sha256


def test_campaign_identity_cannot_be_reused_as_evidence() -> None:
    with pytest.raises(ValueError, match="must not alias"):
        revoke_generated_migration_campaign(
            campaign_decision_sha256="1" * 64,
            reason="experimental_design_invalidated",
            evidence_sha256=["1" * 64],
        )


def test_duplicate_evidence_fails_closed() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        revoke_generated_migration_campaign(
            campaign_decision_sha256="1" * 64,
            reason="manifest_artifact_invalidated",
            evidence_sha256=["2" * 64, "2" * 64],
        )


def test_unknown_reason_fails_closed() -> None:
    with pytest.raises(ValueError, match="not an allowed"):
        revoke_generated_migration_campaign(
            campaign_decision_sha256="1" * 64,
            reason="because_i_said_so",
            evidence_sha256=["2" * 64],
        )
