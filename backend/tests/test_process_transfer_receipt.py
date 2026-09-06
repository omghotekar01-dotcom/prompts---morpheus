from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.process_transfer import ProcessTransferAdmission, inspect_identified_snapshot
from app.process_transfer_receipt import (
    EVIDENCE_STATE,
    RECEIPT_SCHEMA,
    TRUTH_BOUNDARY,
    encode_process_transfer_admission_receipt,
    verify_process_transfer_admission_receipt,
)


SCHEMA = "morpheus-record-schema-v1:" + hashlib.sha256(b"receipt-schema").hexdigest()
CODEC = "morpheus-receipt-test-codec-v1"
ARTIFACT = hashlib.sha256(b"target-artifact").hexdigest()
MANIFEST = hashlib.sha256(b"verification-manifest").hexdigest()


def _frame(value: bytes) -> bytes:
    return str(len(value)).encode() + b"\n" + value + b"\n"


def _snapshot() -> bytes:
    records = [b"first-record", b"second-record"]
    logical = b"MORPHEUS_LOGICAL_INDEX_SNAPSHOT_V1\n2\n" + b"".join(_frame(record) for record in records)
    return (
        b"MORPHEUS_IDENTIFIED_LOGICAL_INDEX_SNAPSHOT_V1\n"
        + _frame(SCHEMA.encode())
        + _frame(CODEC.encode())
        + _frame(logical)
    )


def _admission() -> ProcessTransferAdmission:
    snapshot = _snapshot()
    inspection = inspect_identified_snapshot(
        snapshot,
        expected_schema_identity=SCHEMA,
        expected_codec_identity=CODEC,
    )
    return ProcessTransferAdmission(
        migration_id="migration-7",
        session_id="session-3",
        source_candidate_id="hash-source",
        target_candidate_id="ordered-target",
        schema_identity=SCHEMA,
        codec_identity=CODEC,
        snapshot_sha256=inspection.snapshot_sha256,
        snapshot_size_bytes=inspection.snapshot_size_bytes,
        record_count=inspection.record_count,
        total_record_bytes=inspection.total_record_bytes,
        target_artifact_sha256=ARTIFACT,
        verification_manifest_sha256=MANIFEST,
    )


def _verify(receipt: bytes, snapshot: bytes | None = None, **changes):
    values = dict(
        expected_migration_id="migration-7",
        expected_session_id="session-3",
        expected_target_candidate_id="ordered-target",
        expected_schema_identity=SCHEMA,
        expected_codec_identity=CODEC,
        expected_target_artifact_sha256=ARTIFACT,
        expected_verification_manifest_sha256=MANIFEST,
    )
    values.update(changes)
    return verify_process_transfer_admission_receipt(receipt, snapshot or _snapshot(), **values)


def test_receipt_is_deterministic_canonical_and_replayable() -> None:
    admission = _admission()
    first = encode_process_transfer_admission_receipt(admission)
    second = encode_process_transfer_admission_receipt(admission)
    assert first == second
    assert first.endswith(b"\n")

    decoded = json.loads(first)
    assert decoded["schema"] == RECEIPT_SCHEMA
    assert decoded["automatic_control_allowed"] is False
    assert decoded["activation_allowed"] is False

    evidence = _verify(first)
    assert evidence.receipt_sha256 == hashlib.sha256(first).hexdigest()
    assert evidence.receipt_size_bytes == len(first)
    assert evidence.snapshot_sha256 == admission.snapshot_sha256
    assert evidence.snapshot_size_bytes == admission.snapshot_size_bytes
    assert evidence.target_artifact_sha256 == ARTIFACT
    assert evidence.verification_manifest_sha256 == MANIFEST
    assert evidence.canonical_encoding_verified is True
    assert evidence.snapshot_identity_verified is True
    assert evidence.target_binding_verified is True
    assert evidence.evidence_state == EVIDENCE_STATE
    assert evidence.automatic_control_allowed is False
    assert evidence.activation_allowed is False
    assert "does not authenticate receipt origin" in TRUTH_BOUNDARY


def test_receipt_rejects_snapshot_byte_drift() -> None:
    receipt = encode_process_transfer_admission_receipt(_admission())
    snapshot = bytearray(_snapshot())
    position = snapshot.index(b"first-record")
    snapshot[position] = ord("F")
    with pytest.raises(ValueError, match="snapshot_sha256 does not match supplied snapshot bytes"):
        _verify(receipt, bytes(snapshot))


@pytest.mark.parametrize(
    ("field", "change"),
    [
        ("migration_id", {"expected_migration_id": "migration-other"}),
        ("session_id", {"expected_session_id": "session-other"}),
        ("target_candidate_id", {"expected_target_candidate_id": "other-target"}),
        ("schema_identity", {"expected_schema_identity": "morpheus-record-schema-v1:" + "0" * 64}),
        ("codec_identity", {"expected_codec_identity": "other-codec"}),
        ("target_artifact_sha256", {"expected_target_artifact_sha256": "0" * 64}),
        ("verification_manifest_sha256", {"expected_verification_manifest_sha256": "1" * 64}),
    ],
)
def test_receipt_rejects_expected_identity_drift(field: str, change: dict[str, str]) -> None:
    receipt = encode_process_transfer_admission_receipt(_admission())
    with pytest.raises(ValueError, match=rf"receipt {field} does not match expected identity"):
        _verify(receipt, **change)


def test_receipt_rejects_noncanonical_json_even_when_semantics_match() -> None:
    receipt = encode_process_transfer_admission_receipt(_admission())
    payload = json.loads(receipt)
    noncanonical = json.dumps(payload, indent=2, sort_keys=False).encode() + b"\n"
    with pytest.raises(ValueError, match="receipt bytes are not canonical"):
        _verify(noncanonical)


def test_receipt_rejects_duplicate_json_keys_before_semantic_replay() -> None:
    receipt = encode_process_transfer_admission_receipt(_admission())
    duplicate = receipt.replace(
        b'"migration_id":"migration-7",',
        b'"migration_id":"migration-shadow","migration_id":"migration-7",',
        1,
    )
    with pytest.raises(ValueError, match="receipt contains duplicate JSON key: migration_id"):
        _verify(duplicate)


def test_receipt_rejects_unknown_or_missing_fields() -> None:
    payload = json.loads(encode_process_transfer_admission_receipt(_admission()))
    payload["unexpected"] = "value"
    extra = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    with pytest.raises(ValueError, match="receipt schema fields mismatch"):
        _verify(extra)

    payload.pop("unexpected")
    payload.pop("record_count")
    missing = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    with pytest.raises(ValueError, match="receipt schema fields mismatch"):
        _verify(missing)


def test_receipt_encoder_rejects_authority_drift() -> None:
    with pytest.raises(ValueError, match="cannot encode activation or automatic-control authority"):
        encode_process_transfer_admission_receipt(replace(_admission(), activation_allowed=True))
    with pytest.raises(ValueError, match="cannot encode activation or automatic-control authority"):
        encode_process_transfer_admission_receipt(replace(_admission(), automatic_control_allowed=True))


def test_receipt_rejects_mutated_snapshot_counters_even_with_valid_hash_field() -> None:
    admission = _admission()
    payload = json.loads(encode_process_transfer_admission_receipt(admission))
    payload["record_count"] += 1
    mutated = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    with pytest.raises(ValueError, match="record_count does not match supplied snapshot bytes"):
        _verify(mutated)
