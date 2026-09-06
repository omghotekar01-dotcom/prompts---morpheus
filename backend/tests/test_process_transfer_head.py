from __future__ import annotations

import hashlib

import pytest

from app.process_transfer import ProcessTransferAdmission, inspect_identified_snapshot
from app.process_transfer_head import (
    GENESIS_HEAD_SHA256,
    HEAD_STATE,
    TRUTH_BOUNDARY,
    advance_process_transfer_head,
    load_process_transfer_head,
)
from app.process_transfer_persistence import persist_process_transfer_evidence_bundle
from app.process_transfer_receipt import encode_process_transfer_admission_receipt


SCHEMA = "morpheus-record-schema-v1:" + hashlib.sha256(b"head-schema").hexdigest()
CODEC = "morpheus-head-test-codec-v1"
ARTIFACT = hashlib.sha256(b"head-target-artifact").hexdigest()
MANIFEST = hashlib.sha256(b"head-verification-manifest").hexdigest()


def _frame(value: bytes) -> bytes:
    return str(len(value)).encode() + b"\n" + value + b"\n"


def _snapshot(record: bytes) -> bytes:
    logical = b"MORPHEUS_LOGICAL_INDEX_SNAPSHOT_V1\n1\n" + _frame(record)
    return (
        b"MORPHEUS_IDENTIFIED_LOGICAL_INDEX_SNAPSHOT_V1\n"
        + _frame(SCHEMA.encode())
        + _frame(CODEC.encode())
        + _frame(logical)
    )


def _kwargs(migration_id: str, session_id: str) -> dict[str, str]:
    return {
        "expected_migration_id": migration_id,
        "expected_session_id": session_id,
        "expected_target_candidate_id": "target-generated-index",
        "expected_schema_identity": SCHEMA,
        "expected_codec_identity": CODEC,
        "expected_target_artifact_sha256": ARTIFACT,
        "expected_verification_manifest_sha256": MANIFEST,
    }


def _persist_bundle(tmp_path, *, name: str, migration_id: str, session_id: str, record: bytes):
    snapshot = _snapshot(record)
    inspection = inspect_identified_snapshot(snapshot, expected_schema_identity=SCHEMA, expected_codec_identity=CODEC)
    admission = ProcessTransferAdmission(
        migration_id=migration_id,
        session_id=session_id,
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
    receipt = encode_process_transfer_admission_receipt(admission)
    path = tmp_path / name
    persist_process_transfer_evidence_bundle(path, receipt, snapshot, **_kwargs(migration_id, session_id))
    return path


def test_head_genesis_and_contiguous_advance_are_hash_chained(tmp_path) -> None:
    head = tmp_path / "receiver-head.json"
    first_bundle = _persist_bundle(
        tmp_path,
        name="first.bundle",
        migration_id="migration-head-1",
        session_id="session-head-1",
        record=b"alpha",
    )
    first = advance_process_transfer_head(
        head,
        first_bundle,
        authority_id="receiver-a",
        sequence=1,
        expected_previous_head_sha256=GENESIS_HEAD_SHA256,
        **_kwargs("migration-head-1", "session-head-1"),
    )
    assert first.sequence == 1
    assert first.previous_head_sha256 == GENESIS_HEAD_SHA256
    assert first.evidence_state == HEAD_STATE
    assert first.automatic_control_allowed is False
    assert first.activation_allowed is False

    second_bundle = _persist_bundle(
        tmp_path,
        name="second.bundle",
        migration_id="migration-head-2",
        session_id="session-head-2",
        record=b"beta",
    )
    second = advance_process_transfer_head(
        head,
        second_bundle,
        authority_id="receiver-a",
        sequence=2,
        expected_previous_head_sha256=first.head_sha256,
        **_kwargs("migration-head-2", "session-head-2"),
    )
    document, persisted_sha = load_process_transfer_head(head)
    assert second.previous_head_sha256 == first.head_sha256
    assert persisted_sha == second.head_sha256
    assert document["sequence"] == 2
    assert document["bundle_sha256"] == second.bundle_sha256
    assert "does not authenticate the authority id" in TRUTH_BOUNDARY


def test_head_rejects_replay_and_sequence_gap_without_replacing_current_head(tmp_path) -> None:
    head = tmp_path / "receiver-head.json"
    bundle = _persist_bundle(
        tmp_path,
        name="first.bundle",
        migration_id="migration-head-1",
        session_id="session-head-1",
        record=b"alpha",
    )
    first = advance_process_transfer_head(
        head,
        bundle,
        authority_id="receiver-a",
        sequence=1,
        expected_previous_head_sha256=GENESIS_HEAD_SHA256,
        **_kwargs("migration-head-1", "session-head-1"),
    )
    original = head.read_bytes()

    with pytest.raises(ValueError, match="next contiguous value"):
        advance_process_transfer_head(
            head,
            bundle,
            authority_id="receiver-a",
            sequence=1,
            expected_previous_head_sha256=first.head_sha256,
            **_kwargs("migration-head-1", "session-head-1"),
        )
    assert head.read_bytes() == original

    with pytest.raises(ValueError, match="next contiguous value"):
        advance_process_transfer_head(
            head,
            bundle,
            authority_id="receiver-a",
            sequence=3,
            expected_previous_head_sha256=first.head_sha256,
            **_kwargs("migration-head-1", "session-head-1"),
        )
    assert head.read_bytes() == original


def test_head_rejects_stale_cas_and_authority_drift(tmp_path) -> None:
    head = tmp_path / "receiver-head.json"
    bundle = _persist_bundle(
        tmp_path,
        name="first.bundle",
        migration_id="migration-head-1",
        session_id="session-head-1",
        record=b"alpha",
    )
    first = advance_process_transfer_head(
        head,
        bundle,
        authority_id="receiver-a",
        sequence=1,
        expected_previous_head_sha256=GENESIS_HEAD_SHA256,
        **_kwargs("migration-head-1", "session-head-1"),
    )
    original = head.read_bytes()

    with pytest.raises(ValueError, match="stale process-transfer head compare-and-swap expectation"):
        advance_process_transfer_head(
            head,
            bundle,
            authority_id="receiver-a",
            sequence=2,
            expected_previous_head_sha256=GENESIS_HEAD_SHA256,
            **_kwargs("migration-head-1", "session-head-1"),
        )
    assert head.read_bytes() == original

    with pytest.raises(ValueError, match="authority_id does not match"):
        advance_process_transfer_head(
            head,
            bundle,
            authority_id="receiver-b",
            sequence=2,
            expected_previous_head_sha256=first.head_sha256,
            **_kwargs("migration-head-1", "session-head-1"),
        )
    assert head.read_bytes() == original


def test_head_rejects_bundle_identity_drift_before_write(tmp_path) -> None:
    head = tmp_path / "receiver-head.json"
    bundle = _persist_bundle(
        tmp_path,
        name="first.bundle",
        migration_id="migration-head-1",
        session_id="session-head-1",
        record=b"alpha",
    )
    with pytest.raises(ValueError, match="receipt migration_id does not match expected identity"):
        advance_process_transfer_head(
            head,
            bundle,
            authority_id="receiver-a",
            sequence=1,
            expected_previous_head_sha256=GENESIS_HEAD_SHA256,
            **_kwargs("wrong-migration", "session-head-1"),
        )
    assert not head.exists()
