from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.dataplane import VersionedArtifactRouter
from app.dataplane_recovery import capture_active_route_checkpoint
from app.dataplane_recovery_generation import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    verify_recovery_generation_semantics,
)
from app.dataplane_recovery_interchange import export_recovery_checkpoint
from app.dataplane_recovery_store import publish_recovery_payload
from app.dataplane_recovery_store_rebootstrap import verify_rebootstrap_from_store


def _source_router_with_generation_provenance() -> VersionedArtifactRouter:
    router = VersionedArtifactRouter()
    router.bootstrap(
        "dep-a",
        candidate_id="candidate-a",
        artifact_sha256="a" * 64,
        verification_manifest_sha256="b" * 64,
    )
    router.stage(
        "dep-a",
        candidate_id="candidate-x",
        artifact_sha256="c" * 64,
        verification_manifest_sha256="d" * 64,
    )
    router.activate("dep-a", expected_from_candidate_id="candidate-a", expected_to_candidate_id="candidate-x")
    router.rollback("dep-a", reason="restore source identity before checkpoint")
    router.bootstrap(
        "dep-b",
        candidate_id="candidate-b",
        artifact_sha256="e" * 64,
        verification_manifest_sha256="f" * 64,
    )
    return router


def _fresh_recovered_router() -> VersionedArtifactRouter:
    router = VersionedArtifactRouter()
    router.bootstrap(
        "dep-b",
        candidate_id="candidate-b",
        artifact_sha256="e" * 64,
        verification_manifest_sha256="f" * 64,
    )
    router.bootstrap(
        "dep-a",
        candidate_id="candidate-a",
        artifact_sha256="a" * 64,
        verification_manifest_sha256="b" * 64,
    )
    return router


def _published(tmp_path: Path):
    checkpoint = capture_active_route_checkpoint(_source_router_with_generation_provenance())
    assert [route.source_generation for route in checkpoint.routes] == [3, 1]
    payload = export_recovery_checkpoint(checkpoint)
    target = tmp_path / "state" / "recovery.json"
    store = publish_recovery_payload(target, payload)
    recovered = _fresh_recovered_router()
    p62 = verify_rebootstrap_from_store(target, recovered, store)
    return target, store, recovered, p62


def test_p63_binds_source_generation_provenance_to_fresh_bootstrap_reset_deterministically(tmp_path: Path) -> None:
    target, store, recovered, p62 = _published(tmp_path)
    first = verify_recovery_generation_semantics(target, recovered, store, p62)
    second = verify_recovery_generation_semantics(target, recovered, store, p62)
    assert first == second
    assert first.checkpoint_sha256 == p62.checkpoint_sha256
    assert first.payload_sha256 == p62.payload_sha256
    assert first.route_count == 2
    assert len(first.source_generations_sha256) == 64
    assert len(first.recovered_generations_sha256) == 64
    assert first.source_generations_sha256 != first.recovered_generations_sha256
    assert len(first.generation_binding_sha256) == 64
    assert first.source_generation_provenance_verified is True
    assert first.fresh_bootstrap_generation_verified is True
    assert first.evidence_state == EVIDENCE_STATE
    assert first.automatic_control_allowed is False
    assert first.as_dict()["truth_boundary"] == TRUTH_BOUNDARY


def test_p63_rejects_identity_equivalent_router_that_is_not_fresh_bootstrap_generation(tmp_path: Path) -> None:
    target, store, _, _ = _published(tmp_path)
    recovered = _source_router_with_generation_provenance()
    p62 = verify_rebootstrap_from_store(target, recovered, store)
    with pytest.raises(ValueError, match="fresh-bootstrap generation reset policy"):
        verify_recovery_generation_semantics(target, recovered, store, p62)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_state", "WRONG"),
        ("stored_payload_identity_verified", False),
        ("canonical_interchange_verified", False),
        ("restart_route_consistency_verified", False),
        ("store_rebootstrap_consistency_verified", False),
        ("automatic_control_allowed", True),
        ("checkpoint_sha256", "0" * 64),
        ("payload_sha256", "0" * 64),
        ("payload_size_bytes", 1),
        ("route_count", 1),
        ("binding_sha256", "0" * 64),
    ],
)
def test_p63_rejects_incompatible_or_drifted_p62_evidence(
    tmp_path: Path, field: str, value: object
) -> None:
    target, store, recovered, p62 = _published(tmp_path)
    forged = replace(p62, **{field: value})
    with pytest.raises(ValueError):
        verify_recovery_generation_semantics(target, recovered, store, forged)


def test_p63_preserves_unicode_generation_binding(tmp_path: Path) -> None:
    source = VersionedArtifactRouter()
    source.bootstrap("dep-α", candidate_id="candidate-β", artifact_sha256="a" * 64)
    checkpoint = capture_active_route_checkpoint(source)
    payload = export_recovery_checkpoint(checkpoint)
    target = tmp_path / "unicode.json"
    store = publish_recovery_payload(target, payload)
    recovered = VersionedArtifactRouter()
    recovered.bootstrap("dep-α", candidate_id="candidate-β", artifact_sha256="a" * 64)
    p62 = verify_rebootstrap_from_store(target, recovered, store)
    evidence = verify_recovery_generation_semantics(target, recovered, store, p62)
    assert evidence.route_count == 1
    assert evidence.fresh_bootstrap_generation_verified is True
