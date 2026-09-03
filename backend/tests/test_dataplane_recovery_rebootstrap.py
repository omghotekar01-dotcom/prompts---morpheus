from __future__ import annotations

from dataclasses import replace

import pytest

from app.dataplane import VersionedArtifactRouter
from app.dataplane_recovery import EVIDENCE_STATE as P58_EVIDENCE_STATE
from app.dataplane_recovery import capture_active_route_checkpoint
from app.dataplane_recovery_interchange import EVIDENCE_STATE as P59_EVIDENCE_STATE
from app.dataplane_recovery_interchange import export_recovery_checkpoint
import app.dataplane_recovery_rebootstrap as rebootstrap
from app.dataplane_recovery_rebootstrap import EVIDENCE_STATE, TRUTH_BOUNDARY, verify_rebootstrap_from_interchange


def _source_and_payload():
    source = VersionedArtifactRouter()
    source.bootstrap("dep-b", candidate_id="candidate-b", artifact_sha256="c" * 64, verification_manifest_sha256="d" * 64)
    source.bootstrap("dep-a", candidate_id="candidate-a", artifact_sha256="a" * 64, verification_manifest_sha256="b" * 64)
    checkpoint = capture_active_route_checkpoint(source)
    return checkpoint, export_recovery_checkpoint(checkpoint)


def _recovered() -> VersionedArtifactRouter:
    router = VersionedArtifactRouter()
    router.bootstrap("dep-a", candidate_id="candidate-a", artifact_sha256="a" * 64, verification_manifest_sha256="b" * 64)
    router.bootstrap("dep-b", candidate_id="candidate-b", artifact_sha256="c" * 64, verification_manifest_sha256="d" * 64)
    return router


def test_p60_binds_exact_interchange_to_recovered_router_deterministically() -> None:
    checkpoint, payload = _source_and_payload()
    evidence_a = verify_rebootstrap_from_interchange(payload, _recovered())
    evidence_b = verify_rebootstrap_from_interchange(payload, _recovered())
    assert evidence_a == evidence_b
    assert evidence_a.checkpoint_sha256 == checkpoint.checkpoint_sha256
    assert evidence_a.payload_size_bytes == len(payload)
    assert len(evidence_a.payload_sha256) == 64
    assert len(evidence_a.recovered_routes_sha256) == 64
    assert len(evidence_a.binding_sha256) == 64
    assert evidence_a.route_count == 2
    assert evidence_a.canonical_interchange_verified is True
    assert evidence_a.restart_route_consistency_verified is True
    assert evidence_a.rebootstrap_binding_verified is True
    assert evidence_a.p59_evidence_state == P59_EVIDENCE_STATE
    assert evidence_a.p58_evidence_state == P58_EVIDENCE_STATE
    assert evidence_a.evidence_state == EVIDENCE_STATE
    assert evidence_a.automatic_control_allowed is False
    assert evidence_a.as_dict()["truth_boundary"] == TRUTH_BOUNDARY


def test_p60_rejects_recovered_candidate_and_artifact_drift() -> None:
    _, payload = _source_and_payload()
    candidate_drift = VersionedArtifactRouter()
    candidate_drift.bootstrap("dep-a", candidate_id="candidate-x", artifact_sha256="a" * 64, verification_manifest_sha256="b" * 64)
    candidate_drift.bootstrap("dep-b", candidate_id="candidate-b", artifact_sha256="c" * 64, verification_manifest_sha256="d" * 64)
    with pytest.raises(ValueError, match="candidate identity drift"):
        verify_rebootstrap_from_interchange(payload, candidate_drift)

    artifact_drift = VersionedArtifactRouter()
    artifact_drift.bootstrap("dep-a", candidate_id="candidate-a", artifact_sha256="f" * 64, verification_manifest_sha256="b" * 64)
    artifact_drift.bootstrap("dep-b", candidate_id="candidate-b", artifact_sha256="c" * 64, verification_manifest_sha256="d" * 64)
    with pytest.raises(ValueError, match="artifact identity drift"):
        verify_rebootstrap_from_interchange(payload, artifact_drift)


def test_p60_rejects_manifest_and_inventory_drift() -> None:
    _, payload = _source_and_payload()
    manifest_drift = VersionedArtifactRouter()
    manifest_drift.bootstrap("dep-a", candidate_id="candidate-a", artifact_sha256="a" * 64, verification_manifest_sha256="e" * 64)
    manifest_drift.bootstrap("dep-b", candidate_id="candidate-b", artifact_sha256="c" * 64, verification_manifest_sha256="d" * 64)
    with pytest.raises(ValueError, match="verification-manifest identity drift"):
        verify_rebootstrap_from_interchange(payload, manifest_drift)

    missing = VersionedArtifactRouter()
    missing.bootstrap("dep-a", candidate_id="candidate-a", artifact_sha256="a" * 64, verification_manifest_sha256="b" * 64)
    with pytest.raises(ValueError, match="deployment count"):
        verify_rebootstrap_from_interchange(payload, missing)


def test_p60_rejects_noncanonical_or_tampered_interchange() -> None:
    _, payload = _source_and_payload()
    with pytest.raises(ValueError):
        verify_rebootstrap_from_interchange(payload + b" ", _recovered())
    tampered = payload.replace(b"candidate-a", b"candidate-x", 1)
    with pytest.raises(ValueError):
        verify_rebootstrap_from_interchange(tampered, _recovered())


def test_p60_preserves_unicode_interchange_binding() -> None:
    source = VersionedArtifactRouter()
    source.bootstrap("dep-α", candidate_id="candidate-β", artifact_sha256="a" * 64)
    payload = export_recovery_checkpoint(capture_active_route_checkpoint(source))
    recovered = VersionedArtifactRouter()
    recovered.bootstrap("dep-α", candidate_id="candidate-β", artifact_sha256="a" * 64)
    evidence = verify_rebootstrap_from_interchange(payload, recovered)
    assert evidence.rebootstrap_binding_verified is True
    assert b"\\u03b1" in payload and b"\\u03b2" in payload


def test_p60_rejects_incompatible_p59_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    _, payload = _source_and_payload()
    real_import = rebootstrap.import_recovery_checkpoint

    def bad_import(data: bytes):
        checkpoint, evidence = real_import(data)
        return checkpoint, replace(evidence, evidence_state="OTHER")

    monkeypatch.setattr(rebootstrap, "import_recovery_checkpoint", bad_import)
    with pytest.raises(ValueError, match="P59 interchange evidence has an incompatible evidence state"):
        verify_rebootstrap_from_interchange(payload, _recovered())


def test_p60_rejects_p59_control_or_checkpoint_identity_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    _, payload = _source_and_payload()
    real_import = rebootstrap.import_recovery_checkpoint

    def control_import(data: bytes):
        checkpoint, evidence = real_import(data)
        return checkpoint, replace(evidence, automatic_control_allowed=True)

    monkeypatch.setattr(rebootstrap, "import_recovery_checkpoint", control_import)
    with pytest.raises(ValueError, match="cannot authorize automatic control"):
        verify_rebootstrap_from_interchange(payload, _recovered())

    def drift_import(data: bytes):
        checkpoint, evidence = real_import(data)
        return checkpoint, replace(evidence, checkpoint_sha256="0" * 64)

    monkeypatch.setattr(rebootstrap, "import_recovery_checkpoint", drift_import)
    with pytest.raises(ValueError, match="checkpoint identity drift"):
        verify_rebootstrap_from_interchange(payload, _recovered())


def test_p60_rejects_incompatible_or_unverified_p58_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    _, payload = _source_and_payload()
    real_verify = rebootstrap.verify_recovered_active_routes

    def bad_state(checkpoint, router):
        return replace(real_verify(checkpoint, router), evidence_state="OTHER")

    monkeypatch.setattr(rebootstrap, "verify_recovered_active_routes", bad_state)
    with pytest.raises(ValueError, match="P58 recovery evidence has an incompatible evidence state"):
        verify_rebootstrap_from_interchange(payload, _recovered())

    def unverified(checkpoint, router):
        return replace(real_verify(checkpoint, router), restart_route_consistency_verified=False)

    monkeypatch.setattr(rebootstrap, "verify_recovered_active_routes", unverified)
    with pytest.raises(ValueError, match="not restart-consistency verified"):
        verify_rebootstrap_from_interchange(payload, _recovered())


def test_p60_rejects_p58_control_checkpoint_or_route_count_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    _, payload = _source_and_payload()
    real_verify = rebootstrap.verify_recovered_active_routes

    def control(checkpoint, router):
        return replace(real_verify(checkpoint, router), automatic_control_allowed=True)

    monkeypatch.setattr(rebootstrap, "verify_recovered_active_routes", control)
    with pytest.raises(ValueError, match="cannot authorize automatic control"):
        verify_rebootstrap_from_interchange(payload, _recovered())

    def checkpoint_drift(checkpoint, router):
        return replace(real_verify(checkpoint, router), checkpoint_sha256="0" * 64)

    monkeypatch.setattr(rebootstrap, "verify_recovered_active_routes", checkpoint_drift)
    with pytest.raises(ValueError, match="checkpoint identity drift"):
        verify_rebootstrap_from_interchange(payload, _recovered())

    def count_drift(checkpoint, router):
        return replace(real_verify(checkpoint, router), route_count=999)

    monkeypatch.setattr(rebootstrap, "verify_recovered_active_routes", count_drift)
    with pytest.raises(ValueError, match="route-count drift"):
        verify_rebootstrap_from_interchange(payload, _recovered())
