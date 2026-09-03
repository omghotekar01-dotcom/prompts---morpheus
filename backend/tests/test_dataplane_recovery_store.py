from __future__ import annotations

from pathlib import Path

import pytest

from app.dataplane import VersionedArtifactRouter
from app.dataplane_recovery import capture_active_route_checkpoint
from app.dataplane_recovery_interchange import export_recovery_checkpoint
from app.dataplane_recovery_store import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    load_recovery_payload,
    publish_recovery_payload,
)


def _payload() -> bytes:
    router = VersionedArtifactRouter()
    router.bootstrap("dep-b", candidate_id="candidate-b", artifact_sha256="c" * 64, verification_manifest_sha256="d" * 64)
    router.bootstrap("dep-a", candidate_id="candidate-a", artifact_sha256="a" * 64, verification_manifest_sha256="b" * 64)
    return export_recovery_checkpoint(capture_active_route_checkpoint(router))


def test_p61_publishes_and_loads_exact_payload_deterministically(tmp_path: Path) -> None:
    payload = _payload()
    target = tmp_path / "state" / "recovery.json"
    evidence = publish_recovery_payload(target, payload)
    assert target.read_bytes() == payload
    assert load_recovery_payload(target, expected_payload_sha256=evidence.payload_sha256) == payload
    assert evidence.payload_size_bytes == len(payload)
    assert len(evidence.checkpoint_sha256) == 64
    assert len(evidence.payload_sha256) == 64
    assert evidence.canonical_interchange_verified is True
    assert evidence.same_directory_replace_used is True
    assert evidence.readback_identity_verified is True
    assert evidence.store_consistency_verified is True
    assert evidence.evidence_state == EVIDENCE_STATE
    assert evidence.automatic_control_allowed is False
    assert evidence.as_dict()["truth_boundary"] == TRUTH_BOUNDARY


def test_p61_replaces_existing_file_without_leaving_temp_file(tmp_path: Path) -> None:
    target = tmp_path / "recovery.json"
    target.write_bytes(b"old")
    payload = _payload()
    publish_recovery_payload(target, payload)
    assert target.read_bytes() == payload
    assert list(tmp_path.glob(".recovery.json.morpheus-tmp-*")) == []


def test_p61_rejects_noncanonical_or_tampered_payload_before_publish(tmp_path: Path) -> None:
    payload = _payload()
    target = tmp_path / "recovery.json"
    with pytest.raises(ValueError):
        publish_recovery_payload(target, payload + b" ")
    assert not target.exists()
    tampered = payload.replace(b"candidate-a", b"candidate-x", 1)
    with pytest.raises(ValueError):
        publish_recovery_payload(target, tampered)
    assert not target.exists()


def test_p61_load_rejects_tampered_stored_bytes(tmp_path: Path) -> None:
    target = tmp_path / "recovery.json"
    payload = _payload()
    evidence = publish_recovery_payload(target, payload)
    target.write_bytes(payload.replace(b"candidate-a", b"candidate-x", 1))
    with pytest.raises(ValueError):
        load_recovery_payload(target, expected_payload_sha256=evidence.payload_sha256)


def test_p61_load_rejects_wrong_expected_identity(tmp_path: Path) -> None:
    target = tmp_path / "recovery.json"
    payload = _payload()
    publish_recovery_payload(target, payload)
    with pytest.raises(ValueError, match="does not match expected identity"):
        load_recovery_payload(target, expected_payload_sha256="0" * 64)
    with pytest.raises(ValueError, match="64-character hexadecimal"):
        load_recovery_payload(target, expected_payload_sha256="not-a-digest")


def test_p61_preserves_unicode_canonical_payload(tmp_path: Path) -> None:
    router = VersionedArtifactRouter()
    router.bootstrap("dep-α", candidate_id="candidate-β", artifact_sha256="a" * 64)
    payload = export_recovery_checkpoint(capture_active_route_checkpoint(router))
    target = tmp_path / "unicode.json"
    evidence = publish_recovery_payload(target, payload)
    assert load_recovery_payload(target, expected_payload_sha256=evidence.payload_sha256) == payload
    assert b"\\u03b1" in payload and b"\\u03b2" in payload
