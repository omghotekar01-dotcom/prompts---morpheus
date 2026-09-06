from __future__ import annotations

import hashlib

import pytest

from app.process_transfer import ProcessTransferAdmission, inspect_identified_snapshot
from app.process_transfer_persistence import (
    BUNDLE_MAGIC,
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    encode_process_transfer_evidence_bundle,
    load_process_transfer_evidence_bundle,
    persist_process_transfer_evidence_bundle,
    verify_process_transfer_evidence_bundle,
)
from app.process_transfer_receipt import encode_process_transfer_admission_receipt


SCHEMA = "morpheus-record-schema-v1:" + hashlib.sha256(b"persistence-schema").hexdigest()
CODEC = "morpheus-persistence-test-codec-v1"
ARTIFACT = hashlib.sha256(b"persistence-target-artifact").hexdigest()
MANIFEST = hashlib.sha256(b"persistence-verification-manifest").hexdigest()


def _frame(value: bytes) -> bytes:
    return str(len(value)).encode() + b"\n" + value + b"\n"


def _snapshot() -> bytes:
    records = [b"alpha", b"beta-record"]
    logical = b"MORPHEUS_LOGICAL_INDEX_SNAPSHOT_V1\n2\n" + b"".join(_frame(record) for record in records)
    return (
        b"MORPHEUS_IDENTIFIED_LOGICAL_INDEX_SNAPSHOT_V1\n"
        + _frame(SCHEMA.encode())
        + _frame(CODEC.encode())
        + _frame(logical)
    )


def _receipt() -> bytes:
    snapshot = _snapshot()
    inspection = inspect_identified_snapshot(
        snapshot,
        expected_schema_identity=SCHEMA,
        expected_codec_identity=CODEC,
    )
    admission = ProcessTransferAdmission(
        migration_id="migration-persist-1",
        session_id="session-persist-1",
        source_candidate_id="source-generated-index",
        target_candidate_id="target-generated-index",
        schema_identity=SCHEMA,
        codec_identity=CODEC,
        snapshot_sha256=inspection.snapshot_sha256,
        snapshot_size_bytes=inspection.snapshot_size_bytes,
        record_count=inspection.record_count,
        total_record_bytes=inspection.total_record_bytes,
        target_artifact_sha256=ARTIFACT,
        verification_manifest_sha256=MANIFEST,
    )
    return encode_process_transfer_admission_receipt(admission)


def _kwargs(**changes: str) -> dict[str, str]:
    values = {
        "expected_migration_id": "migration-persist-1",
        "expected_session_id": "session-persist-1",
        "expected_target_candidate_id": "target-generated-index",
        "expected_schema_identity": SCHEMA,
        "expected_codec_identity": CODEC,
        "expected_target_artifact_sha256": ARTIFACT,
        "expected_verification_manifest_sha256": MANIFEST,
    }
    values.update(changes)
    return values


def test_bundle_is_deterministic_and_replays_embedded_evidence() -> None:
    receipt = _receipt()
    snapshot = _snapshot()
    first = encode_process_transfer_evidence_bundle(receipt, snapshot, **_kwargs())
    second = encode_process_transfer_evidence_bundle(receipt, snapshot, **_kwargs())
    assert first == second
    assert first.startswith(BUNDLE_MAGIC)

    evidence = verify_process_transfer_evidence_bundle(first, **_kwargs())
    assert evidence.bundle_sha256 == hashlib.sha256(first).hexdigest()
    assert evidence.bundle_size_bytes == len(first)
    assert evidence.receipt_sha256 == hashlib.sha256(receipt).hexdigest()
    assert evidence.snapshot_sha256 == hashlib.sha256(snapshot).hexdigest()
    assert evidence.bundle_framing_verified is True
    assert evidence.canonical_receipt_verified is True
    assert evidence.snapshot_identity_verified is True
    assert evidence.target_binding_verified is True
    assert evidence.automatic_control_allowed is False
    assert evidence.activation_allowed is False
    assert "does not authenticate receipt origin" in TRUTH_BOUNDARY


def test_bundle_rejects_trailing_and_malformed_framing() -> None:
    bundle = encode_process_transfer_evidence_bundle(_receipt(), _snapshot(), **_kwargs())
    with pytest.raises(ValueError, match="trailing bytes"):
        verify_process_transfer_evidence_bundle(bundle + b"x", **_kwargs())

    malformed = BUNDLE_MAGIC + b"not-a-length\n"
    with pytest.raises(ValueError, match="receipt frame length is invalid"):
        verify_process_transfer_evidence_bundle(malformed, **_kwargs())


def test_bundle_rejects_embedded_snapshot_tampering() -> None:
    bundle = bytearray(encode_process_transfer_evidence_bundle(_receipt(), _snapshot(), **_kwargs()))
    position = bundle.index(b"alpha")
    bundle[position] = ord("A")
    with pytest.raises(ValueError, match="snapshot_sha256 does not match supplied snapshot bytes"):
        verify_process_transfer_evidence_bundle(bytes(bundle), **_kwargs())


def test_persist_round_trip_replaces_target_and_reverifies(tmp_path) -> None:
    target = tmp_path / "handoff.morpheus"
    target.write_bytes(b"old-unverified-data")
    receipt = _receipt()
    snapshot = _snapshot()

    evidence = persist_process_transfer_evidence_bundle(target, receipt, snapshot, **_kwargs())
    persisted = target.read_bytes()
    expected = encode_process_transfer_evidence_bundle(receipt, snapshot, **_kwargs())
    assert persisted == expected
    assert evidence.path == str(target)
    assert evidence.bundle_sha256 == hashlib.sha256(expected).hexdigest()
    assert evidence.file_fsync_completed is True
    assert evidence.atomic_name_replace_completed is True
    assert evidence.post_write_verification_completed is True
    assert evidence.evidence_state == EVIDENCE_STATE
    assert evidence.automatic_control_allowed is False
    assert evidence.activation_allowed is False
    assert not list(tmp_path.glob(f".{target.name}.*.tmp"))

    loaded = load_process_transfer_evidence_bundle(target, **_kwargs())
    assert loaded.bundle_sha256 == evidence.bundle_sha256
    assert loaded.snapshot_sha256 == evidence.snapshot_sha256


def test_failed_prewrite_verification_does_not_replace_existing_target(tmp_path) -> None:
    target = tmp_path / "handoff.morpheus"
    target.write_bytes(b"sentinel")
    with pytest.raises(ValueError, match="receipt migration_id does not match expected identity"):
        persist_process_transfer_evidence_bundle(
            target,
            _receipt(),
            _snapshot(),
            **_kwargs(expected_migration_id="wrong-migration"),
        )
    assert target.read_bytes() == b"sentinel"
    assert not list(tmp_path.glob(f".{target.name}.*.tmp"))


def test_load_rejects_persisted_byte_tampering(tmp_path) -> None:
    target = tmp_path / "handoff.morpheus"
    persist_process_transfer_evidence_bundle(target, _receipt(), _snapshot(), **_kwargs())
    tampered = bytearray(target.read_bytes())
    position = tampered.index(b"beta-record")
    tampered[position] = ord("B")
    target.write_bytes(bytes(tampered))

    with pytest.raises(ValueError, match="snapshot_sha256 does not match supplied snapshot bytes"):
        load_process_transfer_evidence_bundle(target, **_kwargs())


def test_persist_requires_existing_parent_directory(tmp_path) -> None:
    target = tmp_path / "missing" / "handoff.morpheus"
    with pytest.raises(FileNotFoundError, match="parent directory does not exist"):
        persist_process_transfer_evidence_bundle(target, _receipt(), _snapshot(), **_kwargs())
