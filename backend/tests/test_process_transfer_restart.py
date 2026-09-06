from __future__ import annotations

import hashlib

import pytest

from app.process_transfer import ProcessTransferAdmission, inspect_identified_snapshot
from app.process_transfer_head import GENESIS_HEAD_SHA256, HEAD_LOCK_SUFFIX, advance_process_transfer_head
from app.process_transfer_persistence import persist_process_transfer_evidence_bundle
from app.process_transfer_receipt import encode_process_transfer_admission_receipt
from app.process_transfer_restart import RESTART_STATE, TRUTH_BOUNDARY, verify_persisted_process_transfer_restart


SCHEMA = "morpheus-record-schema-v1:" + hashlib.sha256(b"restart-schema").hexdigest()
CODEC = "morpheus-restart-test-codec-v1"
ARTIFACT = hashlib.sha256(b"restart-target-artifact").hexdigest()
MANIFEST = hashlib.sha256(b"restart-verification-manifest").hexdigest()


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


def _restart_kwargs(migration_id: str, session_id: str, *, head_sha256: str, sequence: int = 1) -> dict[str, object]:
    return {
        "expected_authority_id": "receiver-a",
        "expected_sequence": sequence,
        "expected_head_sha256": head_sha256,
        **_kwargs(migration_id, session_id),
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


def _lock_path(head):
    return head.with_name(head.name + HEAD_LOCK_SUFFIX)


def _persist_head(tmp_path):
    head = tmp_path / "receiver-head.json"
    bundle = _persist_bundle(
        tmp_path,
        name="accepted.bundle",
        migration_id="migration-restart-1",
        session_id="session-restart-1",
        record=b"alpha",
    )
    verification = advance_process_transfer_head(
        head,
        bundle,
        authority_id="receiver-a",
        sequence=1,
        expected_previous_head_sha256=GENESIS_HEAD_SHA256,
        **_kwargs("migration-restart-1", "session-restart-1"),
    )
    return head, bundle, verification


def test_restart_reverifies_exact_head_and_bound_bundle_without_activation(tmp_path) -> None:
    head, bundle, advanced = _persist_head(tmp_path)
    head_before = head.read_bytes()
    bundle_before = bundle.read_bytes()

    verified = verify_persisted_process_transfer_restart(
        head,
        bundle,
        **_restart_kwargs("migration-restart-1", "session-restart-1", head_sha256=advanced.head_sha256),
    )

    assert verified.head_sha256 == advanced.head_sha256
    assert verified.bundle_sha256 == advanced.bundle_sha256
    assert verified.sequence == 1
    assert verified.evidence_state == RESTART_STATE
    assert verified.exact_expected_head_verified is True
    assert verified.head_bundle_binding_verified is True
    assert verified.cooperative_writer_exclusion_verified is True
    assert verified.restart_evidence_verified is True
    assert verified.automatic_control_allowed is False
    assert verified.activation_allowed is False
    assert head.read_bytes() == head_before
    assert bundle.read_bytes() == bundle_before
    assert not _lock_path(head).exists()
    assert "does not prove that the caller's expected head is globally fresh or trusted" in TRUTH_BOUNDARY


def test_restart_rejects_stale_expected_head_before_accepting_bundle(tmp_path) -> None:
    head, bundle, advanced = _persist_head(tmp_path)
    wrong_head = hashlib.sha256(b"stale-head").hexdigest()

    with pytest.raises(ValueError, match="does not match exact expected head"):
        verify_persisted_process_transfer_restart(
            head,
            bundle,
            **_restart_kwargs("migration-restart-1", "session-restart-1", head_sha256=wrong_head),
        )

    assert head.read_bytes()
    assert bundle.read_bytes()
    assert not _lock_path(head).exists()
    assert advanced.head_sha256 != wrong_head


def test_restart_rejects_valid_but_different_bundle_bound_to_same_identities(tmp_path) -> None:
    head, bundle, advanced = _persist_head(tmp_path)
    replacement = _persist_bundle(
        tmp_path,
        name="replacement.bundle",
        migration_id="migration-restart-1",
        session_id="session-restart-1",
        record=b"beta",
    )

    with pytest.raises(ValueError, match="does not bind the supplied verified evidence bundle"):
        verify_persisted_process_transfer_restart(
            head,
            replacement,
            **_restart_kwargs("migration-restart-1", "session-restart-1", head_sha256=advanced.head_sha256),
        )

    assert bundle.read_bytes() != replacement.read_bytes()
    assert not _lock_path(head).exists()


def test_restart_rejects_expected_identity_drift_and_releases_lock(tmp_path) -> None:
    head, bundle, advanced = _persist_head(tmp_path)
    kwargs = _restart_kwargs("migration-restart-1", "session-restart-1", head_sha256=advanced.head_sha256)
    kwargs["expected_sequence"] = 2

    with pytest.raises(ValueError, match="sequence does not match expected sequence"):
        verify_persisted_process_transfer_restart(head, bundle, **kwargs)

    assert not _lock_path(head).exists()


def test_restart_fails_closed_on_existing_cooperative_writer_lock_without_deleting_it(tmp_path) -> None:
    head, bundle, advanced = _persist_head(tmp_path)
    lock = _lock_path(head)
    lock.write_bytes(b"held-by-writer")

    with pytest.raises(ValueError, match="cooperative writer lock already exists"):
        verify_persisted_process_transfer_restart(
            head,
            bundle,
            **_restart_kwargs("migration-restart-1", "session-restart-1", head_sha256=advanced.head_sha256),
        )

    assert lock.read_bytes() == b"held-by-writer"


def test_restart_missing_head_fails_closed_and_releases_its_cooperative_lock(tmp_path) -> None:
    head = tmp_path / "missing-head.json"
    bundle = _persist_bundle(
        tmp_path,
        name="accepted.bundle",
        migration_id="migration-restart-1",
        session_id="session-restart-1",
        record=b"alpha",
    )

    with pytest.raises(FileNotFoundError):
        verify_persisted_process_transfer_restart(
            head,
            bundle,
            **_restart_kwargs(
                "migration-restart-1",
                "session-restart-1",
                head_sha256=hashlib.sha256(b"expected-head").hexdigest(),
            ),
        )

    assert not head.exists()
    assert not _lock_path(head).exists()
