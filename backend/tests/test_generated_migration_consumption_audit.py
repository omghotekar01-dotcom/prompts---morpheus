from __future__ import annotations

import pytest

from app.generated_migration_consumption_audit import create_migration_consumption_audit


def test_genesis_audit_is_deterministic() -> None:
    kwargs = dict(
        sequence=0,
        capability="candidate_comparison",
        campaign_decision_sha256="1" * 64,
        consumption_sha256="2" * 64,
        authorized=True,
    )
    first = create_migration_consumption_audit(**kwargs)
    second = create_migration_consumption_audit(**kwargs)
    assert first.audit_sha256 == second.audit_sha256
    assert first.predecessor_audit_sha256 is None


def test_non_genesis_requires_predecessor() -> None:
    with pytest.raises(ValueError, match="predecessor"):
        create_migration_consumption_audit(
            sequence=1,
            capability="publication_claim",
            campaign_decision_sha256="1" * 64,
            consumption_sha256="2" * 64,
            authorized=True,
        )


def test_genesis_rejects_predecessor() -> None:
    with pytest.raises(ValueError, match="genesis"):
        create_migration_consumption_audit(
            sequence=0,
            capability="research_summary",
            campaign_decision_sha256="1" * 64,
            consumption_sha256="2" * 64,
            authorized=True,
            predecessor_audit_sha256="3" * 64,
        )


def test_truthy_authorization_alias_fails_closed() -> None:
    with pytest.raises(ValueError, match="explicitly authorized"):
        create_migration_consumption_audit(
            sequence=0,
            capability="migration_recommendation",
            campaign_decision_sha256="1" * 64,
            consumption_sha256="2" * 64,
            authorized=1,  # type: ignore[arg-type]
        )


def test_boolean_sequence_alias_fails_closed() -> None:
    with pytest.raises(ValueError, match="exact integer"):
        create_migration_consumption_audit(
            sequence=False,  # type: ignore[arg-type]
            capability="candidate_comparison",
            campaign_decision_sha256="1" * 64,
            consumption_sha256="2" * 64,
            authorized=True,
        )


def test_evidence_aliasing_is_rejected() -> None:
    with pytest.raises(ValueError, match="independent"):
        create_migration_consumption_audit(
            sequence=0,
            capability="candidate_comparison",
            campaign_decision_sha256="1" * 64,
            consumption_sha256="1" * 64,
            authorized=True,
        )
