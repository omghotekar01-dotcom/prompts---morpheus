from __future__ import annotations

import pytest

from app.generated_migration_publication_bundle import build_generated_migration_publication_bundle


def _kwargs() -> dict[str, object]:
    return {
        "claim_id": "rq7-publication-claim",
        "capability": "publication_claim",
        "campaign_decision_sha256": "1" * 64,
        "consumption_sha256": "2" * 64,
        "consumption_audit_sha256": "3" * 64,
        "report_sha256": ["4" * 64, "5" * 64, "6" * 64],
        "source_artifact_sha256": ["7" * 64, "8" * 64],
        "revocation_snapshot_sha256": "9" * 64,
        "consumption_authorized": True,
        "active_revocation_count": 0,
    }


def test_publication_bundle_is_order_independent() -> None:
    kwargs = _kwargs()
    first = build_generated_migration_publication_bundle(**kwargs)
    kwargs["report_sha256"] = list(reversed(kwargs["report_sha256"]))  # type: ignore[arg-type]
    kwargs["source_artifact_sha256"] = list(reversed(kwargs["source_artifact_sha256"]))  # type: ignore[arg-type]
    second = build_generated_migration_publication_bundle(**kwargs)
    assert first.publication_ready is True
    assert first.bundle_sha256 == second.bundle_sha256


def test_active_revocation_blocks_publication() -> None:
    kwargs = _kwargs()
    kwargs["active_revocation_count"] = 1
    with pytest.raises(ValueError, match="active campaign revocation"):
        build_generated_migration_publication_bundle(**kwargs)


def test_truthy_authorization_alias_fails_closed() -> None:
    kwargs = _kwargs()
    kwargs["consumption_authorized"] = 1
    with pytest.raises(ValueError, match="explicitly authorized"):
        build_generated_migration_publication_bundle(**kwargs)


def test_boolean_revocation_count_alias_fails_closed() -> None:
    kwargs = _kwargs()
    kwargs["active_revocation_count"] = False
    with pytest.raises(ValueError, match="exact integer"):
        build_generated_migration_publication_bundle(**kwargs)


def test_less_than_three_reports_is_rejected() -> None:
    kwargs = _kwargs()
    kwargs["report_sha256"] = ["4" * 64, "5" * 64]
    with pytest.raises(ValueError, match="at least three"):
        build_generated_migration_publication_bundle(**kwargs)


def test_cross_domain_evidence_aliasing_is_rejected() -> None:
    kwargs = _kwargs()
    kwargs["source_artifact_sha256"] = ["4" * 64]
    with pytest.raises(ValueError, match="independent"):
        build_generated_migration_publication_bundle(**kwargs)
