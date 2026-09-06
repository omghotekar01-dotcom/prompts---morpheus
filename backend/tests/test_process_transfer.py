from __future__ import annotations

import hashlib

import pytest

from app.migration import MigrationController
from app.process_transfer import admit_verified_process_transfer, inspect_identified_snapshot


SCHEMA = "morpheus-record-schema-v1:" + "1" * 64
OTHER_SCHEMA = "morpheus-record-schema-v1:" + "2" * 64
CODEC = "test-codec-v1"
ARTIFACT = "a" * 64
MANIFEST = "b" * 64


def _frame(value: bytes) -> bytes:
    return str(len(value)).encode("ascii") + b"\n" + value + b"\n"


def _logical_snapshot(*records: bytes) -> bytes:
    body = b"MORPHEUS_LOGICAL_INDEX_SNAPSHOT_V1\n" + str(len(records)).encode("ascii") + b"\n"
    return body + b"".join(_frame(record) for record in records)


def _identified_snapshot(*records: bytes, schema: str = SCHEMA, codec: str = CODEC) -> bytes:
    inner = _logical_snapshot(*records)
    return (
        b"MORPHEUS_IDENTIFIED_LOGICAL_INDEX_SNAPSHOT_V1\n"
        + _frame(schema.encode("utf-8"))
        + _frame(codec.encode("utf-8"))
        + _frame(inner)
    )


def _verified_migration() -> tuple[MigrationController, dict[str, object]]:
    controller = MigrationController()
    controller.plan(
        "process-transfer-1",
        session_id="session-1",
        from_candidate_id="candidate-old",
        to_candidate_id="candidate-new",
    )
    controller.shadow_built("process-transfer-1", artifact_sha256=ARTIFACT)
    verified = controller.verify(
        "process-transfer-1",
        compile_verified=True,
        correctness_verified=True,
        verification_manifest_sha256=MANIFEST,
    )
    assert verified["state"] == "VERIFIED"
    return controller, verified


def test_inspection_validates_identity_and_inner_snapshot_without_decoding() -> None:
    payload = _identified_snapshot(b"alpha", b"", b"gamma")
    inspected = inspect_identified_snapshot(
        payload, expected_schema_identity=SCHEMA, expected_codec_identity=CODEC
    )
    assert inspected.record_count == 3
    assert inspected.total_record_bytes == 10
    assert inspected.snapshot_size_bytes == len(payload)
    assert inspected.snapshot_sha256 == hashlib.sha256(payload).hexdigest()

    with pytest.raises(ValueError, match="schema identity mismatch"):
        inspect_identified_snapshot(payload, expected_schema_identity=OTHER_SCHEMA, expected_codec_identity=CODEC)
    with pytest.raises(ValueError, match="codec identity mismatch"):
        inspect_identified_snapshot(payload, expected_schema_identity=SCHEMA, expected_codec_identity="other-codec")


def test_verified_migration_can_admit_snapshot_without_mutating_or_activating() -> None:
    controller, verified = _verified_migration()
    before = controller.get("process-transfer-1")
    payload = _identified_snapshot(b"one", b"two")

    admission = admit_verified_process_transfer(
        verified,
        payload,
        source_schema_identity=SCHEMA,
        target_schema_identity=SCHEMA,
        codec_identity=CODEC,
    )

    assert controller.get("process-transfer-1") == before
    assert admission.migration_id == "process-transfer-1"
    assert admission.source_candidate_id == "candidate-old"
    assert admission.target_candidate_id == "candidate-new"
    assert admission.snapshot_sha256 == hashlib.sha256(payload).hexdigest()
    assert admission.record_count == 2
    assert admission.target_artifact_sha256 == ARTIFACT
    assert admission.verification_manifest_sha256 == MANIFEST
    assert admission.automatic_control_allowed is False
    assert admission.activation_allowed is False
    assert admission.evidence_state == "VERIFIED_LOGICAL_PROCESS_TRANSFER_ADMITTED_NO_ACTIVATION"
    assert "no record decoding" in admission.truth_boundary.lower()
    assert "no" in admission.truth_boundary.lower() and "live process swap" in admission.truth_boundary.lower()


def test_process_transfer_rejects_unverified_or_internally_inconsistent_migration() -> None:
    controller = MigrationController()
    planned = controller.plan(
        "not-ready",
        session_id="session-1",
        from_candidate_id="old",
        to_candidate_id="new",
    )
    payload = _identified_snapshot(b"one")
    with pytest.raises(ValueError, match="state VERIFIED"):
        admit_verified_process_transfer(
            planned,
            payload,
            source_schema_identity=SCHEMA,
            target_schema_identity=SCHEMA,
            codec_identity=CODEC,
        )

    _, verified = _verified_migration()
    forged = dict(verified)
    forged["compile_verified"] = False
    with pytest.raises(ValueError, match="compile and correctness"):
        admit_verified_process_transfer(
            forged,
            payload,
            source_schema_identity=SCHEMA,
            target_schema_identity=SCHEMA,
            codec_identity=CODEC,
        )

    forged = dict(verified)
    forged["artifact_sha256"] = "not-a-digest"
    with pytest.raises(ValueError, match="artifact_sha256"):
        admit_verified_process_transfer(
            forged,
            payload,
            source_schema_identity=SCHEMA,
            target_schema_identity=SCHEMA,
            codec_identity=CODEC,
        )


def test_process_transfer_rejects_schema_mismatch_and_malformed_snapshot_bytes() -> None:
    _, verified = _verified_migration()
    payload = _identified_snapshot(b"one")

    with pytest.raises(ValueError, match="schemas are incompatible"):
        admit_verified_process_transfer(
            verified,
            payload,
            source_schema_identity=SCHEMA,
            target_schema_identity=OTHER_SCHEMA,
            codec_identity=CODEC,
        )

    with pytest.raises(ValueError, match="canonical generated-record"):
        admit_verified_process_transfer(
            verified,
            payload,
            source_schema_identity="schema-v1",
            target_schema_identity="schema-v1",
            codec_identity=CODEC,
        )

    with pytest.raises(ValueError, match="trailing bytes"):
        admit_verified_process_transfer(
            verified,
            payload + b"x",
            source_schema_identity=SCHEMA,
            target_schema_identity=SCHEMA,
            codec_identity=CODEC,
        )

    broken_inner = (
        b"MORPHEUS_IDENTIFIED_LOGICAL_INDEX_SNAPSHOT_V1\n"
        + _frame(SCHEMA.encode())
        + _frame(CODEC.encode())
        + _frame(b"MORPHEUS_LOGICAL_INDEX_SNAPSHOT_V1\n1\n5\nabc\n")
    )
    with pytest.raises(ValueError, match="truncated|delimiter"):
        admit_verified_process_transfer(
            verified,
            broken_inner,
            source_schema_identity=SCHEMA,
            target_schema_identity=SCHEMA,
            codec_identity=CODEC,
        )
