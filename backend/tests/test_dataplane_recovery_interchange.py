from __future__ import annotations

import json
from dataclasses import replace

import pytest

from app.dataplane import VersionedArtifactRouter
from app.dataplane_recovery import capture_active_route_checkpoint
from app.dataplane_recovery_interchange import EVIDENCE_STATE, INTERCHANGE_SCHEMA, TRUTH_BOUNDARY, export_recovery_checkpoint, import_recovery_checkpoint


def _checkpoint():
    router = VersionedArtifactRouter()
    router.bootstrap("dep-b", candidate_id="candidate-b", artifact_sha256="c" * 64, verification_manifest_sha256="d" * 64)
    router.bootstrap("dep-a", candidate_id="candidate-a", artifact_sha256="a" * 64, verification_manifest_sha256="b" * 64)
    return capture_active_route_checkpoint(router)


def test_p59_interchange_is_deterministic_and_exactly_roundtrips() -> None:
    checkpoint = _checkpoint()
    payload_a = export_recovery_checkpoint(checkpoint)
    payload_b = export_recovery_checkpoint(checkpoint)
    assert payload_a == payload_b
    assert payload_a == json.dumps(json.loads(payload_a), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    restored, evidence = import_recovery_checkpoint(payload_a)
    assert restored == checkpoint
    assert export_recovery_checkpoint(restored) == payload_a
    assert evidence.interchange_schema == INTERCHANGE_SCHEMA
    assert evidence.checkpoint_sha256 == checkpoint.checkpoint_sha256
    assert evidence.payload_size_bytes == len(payload_a)
    assert evidence.canonical_roundtrip_verified is True
    assert evidence.evidence_state == EVIDENCE_STATE
    assert evidence.automatic_control_allowed is False
    assert len(evidence.payload_sha256) == 64
    assert evidence.as_dict()["truth_boundary"] == TRUTH_BOUNDARY


def test_p59_preserves_p58_hash_semantics_for_unicode_identifiers() -> None:
    router = VersionedArtifactRouter()
    router.bootstrap("dep-α", candidate_id="candidate-β", artifact_sha256="a" * 64)
    checkpoint = capture_active_route_checkpoint(router)
    payload = export_recovery_checkpoint(checkpoint)
    restored, evidence = import_recovery_checkpoint(payload)
    assert restored == checkpoint
    assert evidence.checkpoint_sha256 == checkpoint.checkpoint_sha256
    assert b"\\u03b1" in payload and b"\\u03b2" in payload


def test_p59_rejects_noncanonical_json_bytes() -> None:
    payload = export_recovery_checkpoint(_checkpoint())
    pretty = json.dumps(json.loads(payload), indent=2).encode("utf-8")
    with pytest.raises(ValueError, match="not canonical"):
        import_recovery_checkpoint(pretty)


def test_p59_rejects_unknown_or_missing_fields() -> None:
    parsed = json.loads(export_recovery_checkpoint(_checkpoint()))
    parsed["unexpected"] = True
    with pytest.raises(ValueError, match="keys do not match schema"):
        import_recovery_checkpoint(json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode())
    parsed = json.loads(export_recovery_checkpoint(_checkpoint()))
    del parsed["checkpoint"]["route_count"]
    with pytest.raises(ValueError, match="keys do not match schema"):
        import_recovery_checkpoint(json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode())


def test_p59_rejects_schema_and_control_drift() -> None:
    parsed = json.loads(export_recovery_checkpoint(_checkpoint()))
    parsed["schema"] = "other"
    with pytest.raises(ValueError, match="incompatible schema"):
        import_recovery_checkpoint(json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode())
    parsed = json.loads(export_recovery_checkpoint(_checkpoint()))
    parsed["automatic_control_allowed"] = True
    with pytest.raises(ValueError, match="cannot authorize automatic control"):
        import_recovery_checkpoint(json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode())


def test_p59_rejects_checkpoint_hash_and_inventory_drift() -> None:
    parsed = json.loads(export_recovery_checkpoint(_checkpoint()))
    parsed["checkpoint"]["checkpoint_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="does not match checkpoint_sha256"):
        import_recovery_checkpoint(json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode())
    parsed = json.loads(export_recovery_checkpoint(_checkpoint()))
    parsed["checkpoint"]["route_count"] += 1
    with pytest.raises(ValueError, match="route_count"):
        import_recovery_checkpoint(json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode())


def test_p59_rejects_route_identity_and_generation_drift() -> None:
    parsed = json.loads(export_recovery_checkpoint(_checkpoint()))
    parsed["checkpoint"]["routes"][0]["artifact_sha256"] = "z" * 64
    with pytest.raises(ValueError, match="64-character hexadecimal"):
        import_recovery_checkpoint(json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode())
    parsed = json.loads(export_recovery_checkpoint(_checkpoint()))
    parsed["checkpoint"]["routes"][0]["source_generation"] = True
    with pytest.raises(ValueError, match="positive integer"):
        import_recovery_checkpoint(json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode())


def test_p59_rejects_invalid_bytes_and_json() -> None:
    with pytest.raises(ValueError, match="non-empty bytes"):
        import_recovery_checkpoint(b"")
    with pytest.raises(ValueError, match="valid UTF-8"):
        import_recovery_checkpoint(b"\xff")
    with pytest.raises(ValueError, match="valid JSON"):
        import_recovery_checkpoint(b"{")


def test_p59_export_rejects_invalid_p58_state() -> None:
    checkpoint = _checkpoint()
    with pytest.raises(ValueError, match="cannot authorize automatic control"):
        export_recovery_checkpoint(replace(checkpoint, automatic_control_allowed=True))
    with pytest.raises(ValueError, match="does not match checkpoint_sha256"):
        export_recovery_checkpoint(replace(checkpoint, checkpoint_sha256="0" * 64))
