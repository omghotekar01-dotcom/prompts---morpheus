from __future__ import annotations

import pytest

from app.generated_migration_campaign_consumption import consume_generated_migration_campaign


def test_promoted_unrevoked_campaign_can_be_consumed() -> None:
    result = consume_generated_migration_campaign(
        campaign_decision_sha256="1" * 64,
        promoted=True,
        capability="candidate_comparison",
    )
    assert result.authorized is True
    assert len(result.consumption_sha256) == 64


def test_active_matching_revocation_fails_closed() -> None:
    with pytest.raises(ValueError, match="active revocation"):
        consume_generated_migration_campaign(
            campaign_decision_sha256="1" * 64,
            promoted=True,
            capability="publication_claim",
            revocations=[{
                "revoked": True,
                "campaign_decision_sha256": "1" * 64,
                "revocation_sha256": "2" * 64,
            }],
        )


def test_other_campaign_revocation_does_not_contaminate_decision() -> None:
    result = consume_generated_migration_campaign(
        campaign_decision_sha256="1" * 64,
        promoted=True,
        capability="research_summary",
        revocations=[{
            "revoked": True,
            "campaign_decision_sha256": "3" * 64,
            "revocation_sha256": "2" * 64,
        }],
    )
    assert result.authorized is True


def test_truthy_promotion_alias_fails_closed() -> None:
    with pytest.raises(ValueError, match="explicitly promoted"):
        consume_generated_migration_campaign(
            campaign_decision_sha256="1" * 64,
            promoted=1,  # type: ignore[arg-type]
            capability="migration_recommendation",
        )


def test_truthy_revocation_alias_fails_closed() -> None:
    with pytest.raises(ValueError, match="exact boolean"):
        consume_generated_migration_campaign(
            campaign_decision_sha256="1" * 64,
            promoted=True,
            capability="migration_recommendation",
            revocations=[{
                "revoked": 1,
                "campaign_decision_sha256": "1" * 64,
                "revocation_sha256": "2" * 64,
            }],
        )
