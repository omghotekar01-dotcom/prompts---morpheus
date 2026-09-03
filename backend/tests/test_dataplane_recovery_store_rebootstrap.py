from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.dataplane import VersionedArtifactRouter
from app.dataplane_recovery import capture_active_route_checkpoint
from app.dataplane_recovery_interchange import export_recovery_checkpoint
from app.dataplane_recovery_store import publish_recovery_payload
from app.dataplane_recovery_store_rebootstrap import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    verify_rebootstrap_from_store,
)


def _source_router() -> VersionedArtifactRouter:
    router = VersionedArtifactRouter()
    router.bootstrap(
        "dep-b",
        candidate_id="candidate-b",
        artifact_sha256="c" * 64,
        verification_manifest_sha256="d" * 64,
    )
    router.bootstrap(
        "dep-a",
        candidate_id="candidate-a",
        artifact_sha256="a" * 64,
        verification_manifest_sha256="b" * 64,
    )
    return router


def _recovered_router() -> VersionedArtifactRouter:
    return _source_router()


def _published(tmp_path: Path):
    payload = export_recovery_checkpoint(capture_active_route_checkpoint(_source_router()))
    target = tmp_path / "state" / "recovery.json"
    evidence = publish_recovery_payload(target, payload)
    return target, payload, evidence


def test_p62_binds_exact_stored_bytes_to_recovered_router_deterministically(tmp_path: Path) -> None:
    target, payload, store = _published(tmp_path)
    first = verify_rebootstrap_from_store(target, _recovered_router(), store)
    second = verify_rebootstrap_from_store(target, _recovered_router(), store)
    assert first == second
    assert first.checkpoint_sha256 == store.checkpoint_sha256
    assert first.payload_sha256 == store.payload_sha256
    assert first.payload_size_bytes == len(payload)
    assert first.route_count == 2
    assert len(first.recovered_routes_sha256) == 64
    assert len(first.binding_sha256) == 64
    assert first.stored_payload_identity_verified is True
    assert first.canonical_interchange_verified is True
    assert first.restart_route_consistency_verified is True
    assert first.store_rebootstrap_consistency_verified is True
    assert first.evidence_state == EVIDENCE_STATE
    assert first.automatic_control_allowed is False
    assert first.as_dict()["truth_boundary"] == TRUTH_BOUNDARY


def test_p62_rejects_stored_byte_tampering(tmp_path: Path) -> None:
    target, payload, store = _published(tmp_path)
    target.write_bytes(payload.replace(b"candidate-a", b"candidate-x", 1))
    with pytest.raises(ValueError):
        verify_rebootstrap_from_store(target, _recovered_router(), store)


def test_p62_rejects_recovered_route_identity_drift(tmp_path: Path) -> None:
    target, _, store = _published(tmp_path)
    recovered = VersionedArtifactRouter()
    recovered.bootstrap("dep-b", candidate_id="candidate-b", artifact_sha256="c" * 64, verification_manifest_sha256="d" * 64)
    recovered.bootstrap("dep-a", candidate_id="candidate-x", artifact_sha256="a" * 64, verification_manifest_sha256="b" * 64)
    with pytest.raises(ValueError):
        verify_rebootstrap_from_store(target, recovered, store)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_state", "WRONG"),
        ("canonical_interchange_verified", False),
        ("same_directory_replace_used", False),
        ("readback_identity_verified", False),
        ("store_consistency_verified", False),
        ("automatic_control_allowed", True),
        ("checkpoint_sha256", "0" * 64),
        ("payload_sha256", "0" * 64),
        ("payload_size_bytes", 1),
    ],
)
def test_p62_rejects_incompatible_or_drifted_p61_evidence(tmp_path: Path, field: str, value: object) -> None:
    target, _, store = _published(tmp_path)
    forged = replace(store, **{field: value})
    with pytest.raises(ValueError):
        verify_rebootstrap_from_store(target, _recovered_router(), forged)


def test_p62_preserves_unicode_canonical_store_binding(tmp_path: Path) -> None:
    source = VersionedArtifactRouter()
    source.bootstrap("dep-α", candidate_id="candidate-β", artifact_sha256="a" * 64)
    payload = export_recovery_checkpoint(capture_active_route_checkpoint(source))
    target = tmp_path / "unicode.json"
    store = publish_recovery_payload(target, payload)
    recovered = VersionedArtifactRouter()
    recovered.bootstrap("dep-α", candidate_id="candidate-β", artifact_sha256="a" * 64)
    evidence = verify_rebootstrap_from_store(target, recovered, store)
    assert evidence.payload_sha256 == store.payload_sha256
    assert evidence.store_rebootstrap_consistency_verified is True
