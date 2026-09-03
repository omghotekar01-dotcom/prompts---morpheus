from __future__ import annotations

from dataclasses import replace

import pytest

from app.dataplane import VersionedArtifactRouter
from app.dataplane_recovery import (
    CHECKPOINT_SCHEMA,
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    capture_active_route_checkpoint,
    verify_recovered_active_routes,
)


def _router() -> VersionedArtifactRouter:
    router = VersionedArtifactRouter()
    router.bootstrap(
        "dep-a",
        candidate_id="candidate-a",
        artifact_sha256="a" * 64,
        verification_manifest_sha256="b" * 64,
        metadata={"source": "test"},
    )
    router.bootstrap(
        "dep-b",
        candidate_id="candidate-b",
        artifact_sha256="c" * 64,
        verification_manifest_sha256="d" * 64,
    )
    return router


def _recovered() -> VersionedArtifactRouter:
    router = VersionedArtifactRouter()
    router.bootstrap(
        "dep-a",
        candidate_id="candidate-a",
        artifact_sha256="a" * 64,
        verification_manifest_sha256="b" * 64,
    )
    router.bootstrap(
        "dep-b",
        candidate_id="candidate-b",
        artifact_sha256="c" * 64,
        verification_manifest_sha256="d" * 64,
    )
    return router


def test_p58_checkpoint_and_recovery_are_deterministic() -> None:
    checkpoint_a = capture_active_route_checkpoint(_router())
    checkpoint_b = capture_active_route_checkpoint(_router())
    assert checkpoint_a == checkpoint_b
    assert checkpoint_a.schema == CHECKPOINT_SCHEMA
    assert checkpoint_a.route_count == 2
    assert checkpoint_a.quiescent_routes_verified is True
    assert checkpoint_a.automatic_control_allowed is False
    assert len(checkpoint_a.checkpoint_sha256) == 64
    assert checkpoint_a.as_dict()["truth_boundary"] == TRUTH_BOUNDARY

    verified_a = verify_recovered_active_routes(checkpoint_a, _recovered())
    verified_b = verify_recovered_active_routes(checkpoint_a, _recovered())
    assert verified_a == verified_b
    assert verified_a.evidence_state == EVIDENCE_STATE
    assert verified_a.restart_route_consistency_verified is True
    assert verified_a.automatic_control_allowed is False
    assert len(verified_a.recovered_routes_sha256) == 64
    assert verified_a.as_dict()["truth_boundary"] == TRUTH_BOUNDARY


def test_p58_checkpoint_is_order_independent() -> None:
    first = VersionedArtifactRouter()
    first.bootstrap("b", candidate_id="cb", artifact_sha256="b" * 64)
    first.bootstrap("a", candidate_id="ca", artifact_sha256="a" * 64)
    second = VersionedArtifactRouter()
    second.bootstrap("a", candidate_id="ca", artifact_sha256="a" * 64)
    second.bootstrap("b", candidate_id="cb", artifact_sha256="b" * 64)
    assert capture_active_route_checkpoint(first) == capture_active_route_checkpoint(second)


def test_p58_rejects_staged_or_rollback_state() -> None:
    staged = _router()
    staged.stage(
        "dep-a",
        candidate_id="candidate-new",
        artifact_sha256="e" * 64,
        verification_manifest_sha256="f" * 64,
    )
    with pytest.raises(ValueError, match="requires quiescence"):
        capture_active_route_checkpoint(staged)

    rollback = _router()
    rollback.stage(
        "dep-a",
        candidate_id="candidate-new",
        artifact_sha256="e" * 64,
        verification_manifest_sha256="f" * 64,
    )
    rollback.activate("dep-a", expected_from_candidate_id="candidate-a", expected_to_candidate_id="candidate-new")
    with pytest.raises(ValueError, match="would be lossy"):
        capture_active_route_checkpoint(rollback)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema", "other", "incompatible schema"),
        ("quiescent_routes_verified", False, "must have verified quiescent routes"),
        ("automatic_control_allowed", True, "cannot authorize automatic control"),
        ("route_count", 3, "route_count does not match route inventory"),
        ("checkpoint_sha256", "0" * 64, "does not match checkpoint_sha256"),
    ],
)
def test_p58_rejects_invalid_checkpoint_state(field: str, value: object, message: str) -> None:
    checkpoint = capture_active_route_checkpoint(_router())
    with pytest.raises(ValueError, match=message):
        verify_recovered_active_routes(replace(checkpoint, **{field: value}), _recovered())


def test_p58_rejects_missing_extra_and_identity_drift() -> None:
    checkpoint = capture_active_route_checkpoint(_router())

    missing = VersionedArtifactRouter()
    missing.bootstrap("dep-a", candidate_id="candidate-a", artifact_sha256="a" * 64, verification_manifest_sha256="b" * 64)
    with pytest.raises(ValueError, match="deployment count"):
        verify_recovered_active_routes(checkpoint, missing)

    extra = _recovered()
    extra.bootstrap("dep-c", candidate_id="candidate-c", artifact_sha256="e" * 64)
    with pytest.raises(ValueError, match="deployment count"):
        verify_recovered_active_routes(checkpoint, extra)

    wrong_candidate = VersionedArtifactRouter()
    wrong_candidate.bootstrap("dep-a", candidate_id="other", artifact_sha256="a" * 64, verification_manifest_sha256="b" * 64)
    wrong_candidate.bootstrap("dep-b", candidate_id="candidate-b", artifact_sha256="c" * 64, verification_manifest_sha256="d" * 64)
    with pytest.raises(ValueError, match="candidate identity drift"):
        verify_recovered_active_routes(checkpoint, wrong_candidate)

    wrong_artifact = VersionedArtifactRouter()
    wrong_artifact.bootstrap("dep-a", candidate_id="candidate-a", artifact_sha256="f" * 64, verification_manifest_sha256="b" * 64)
    wrong_artifact.bootstrap("dep-b", candidate_id="candidate-b", artifact_sha256="c" * 64, verification_manifest_sha256="d" * 64)
    with pytest.raises(ValueError, match="artifact identity drift"):
        verify_recovered_active_routes(checkpoint, wrong_artifact)

    wrong_manifest = VersionedArtifactRouter()
    wrong_manifest.bootstrap("dep-a", candidate_id="candidate-a", artifact_sha256="a" * 64, verification_manifest_sha256="f" * 64)
    wrong_manifest.bootstrap("dep-b", candidate_id="candidate-b", artifact_sha256="c" * 64, verification_manifest_sha256="d" * 64)
    with pytest.raises(ValueError, match="verification-manifest identity drift"):
        verify_recovered_active_routes(checkpoint, wrong_manifest)


def test_p58_rejects_non_quiescent_recovered_router() -> None:
    checkpoint = capture_active_route_checkpoint(_router())
    recovered = _recovered()
    recovered.stage(
        "dep-a",
        candidate_id="candidate-new",
        artifact_sha256="e" * 64,
        verification_manifest_sha256="f" * 64,
    )
    with pytest.raises(ValueError, match="unexpectedly has a staged version"):
        verify_recovered_active_routes(checkpoint, recovered)
