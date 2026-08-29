from types import SimpleNamespace

import pytest

from app.generated_migration_reproduction_campaign import promote_generated_migration_reproduction_campaign


def h(ch: str) -> str:
    return ch * 64


def receipt(i: int, *, release: str = h("a"), verified=True):
    groups = [
        ("b", "c", "d", "e"),
        ("f", "1", "2", "3"),
        ("4", "5", "6", "7"),
    ]
    r, env, out, result = groups[i]
    return SimpleNamespace(
        reproduction_verified=verified,
        receipt_sha256=h(r),
        release_manifest_sha256=release,
        runner_environment_sha256=h(env),
        stdout_artifact_sha256=h(out),
        result_artifact_sha256=h(result),
    )


def test_three_independent_runs_promote_and_order_is_irrelevant():
    runs = [receipt(0), receipt(1), receipt(2)]
    a = promote_generated_migration_reproduction_campaign(receipts=runs)
    b = promote_generated_migration_reproduction_campaign(receipts=reversed(runs))
    assert a.reproduction_campaign_verified is True
    assert a.schema == "morpheus.generated_migration_reproduction_campaign.v2"
    assert a.stdout_artifact_sha256s == tuple(sorted(run.stdout_artifact_sha256 for run in runs))
    assert a.campaign_sha256 == b.campaign_sha256


def test_stdout_evidence_change_changes_campaign_identity():
    baseline = [receipt(0), receipt(1), receipt(2)]
    changed = [receipt(0), receipt(1), receipt(2)]
    changed[2].stdout_artifact_sha256 = h("8")
    a = promote_generated_migration_reproduction_campaign(receipts=baseline)
    b = promote_generated_migration_reproduction_campaign(receipts=changed)
    assert a.campaign_sha256 != b.campaign_sha256
    assert a.stdout_artifact_sha256s != b.stdout_artifact_sha256s


def test_release_drift_fails_closed():
    runs = [receipt(0), receipt(1), receipt(2, release=h("9"))]
    with pytest.raises(ValueError, match="same release"):
        promote_generated_migration_reproduction_campaign(receipts=runs)


def test_reused_environment_fails_closed():
    runs = [receipt(0), receipt(1), receipt(2)]
    runs[2].runner_environment_sha256 = runs[0].runner_environment_sha256
    with pytest.raises(ValueError, match="environment"):
        promote_generated_migration_reproduction_campaign(receipts=runs)


def test_reused_stdout_evidence_fails_closed():
    runs = [receipt(0), receipt(1), receipt(2)]
    runs[2].stdout_artifact_sha256 = runs[0].stdout_artifact_sha256
    with pytest.raises(ValueError, match="stdout"):
        promote_generated_migration_reproduction_campaign(receipts=runs)


def test_truthy_non_boolean_verification_fails_closed():
    runs = [receipt(0), receipt(1), receipt(2, verified=1)]
    with pytest.raises(ValueError, match="explicitly"):
        promote_generated_migration_reproduction_campaign(receipts=runs)


def test_boolean_minimum_runs_is_rejected():
    with pytest.raises(ValueError, match="exact integer"):
        promote_generated_migration_reproduction_campaign(receipts=[receipt(0), receipt(1), receipt(2)], minimum_runs=True)
