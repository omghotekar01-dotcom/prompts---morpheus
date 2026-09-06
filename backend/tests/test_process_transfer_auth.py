from __future__ import annotations

import hashlib

import pytest

from app.process_transfer import ProcessTransferAdmission, inspect_identified_snapshot
from app.process_transfer_auth import (
    AUTHENTICATED_RESTART_STATE,
    TRUTH_BOUNDARY,
    create_process_transfer_restart_authentication_tag,
    verify_authenticated_persisted_process_transfer_restart,
)
from app.process_transfer_head import GENESIS_HEAD_SHA256, HEAD_LOCK_SUFFIX, advance_process_transfer_head
from app.process_transfer_persistence import persist_process_transfer_evidence_bundle
from app.process_transfer_receipt import encode_process_transfer_admission_receipt


SCHEMA = "morpheus-record-schema-v1:" + hashlib.sha256(b"auth-restart-schema").hexdigest()
CODEC = "morpheus-auth-restart-test-codec-v1"
ARTIFACT = hashlib.sha256(b"auth-restart-target-artifact").hexdigest()
MANIFEST = hashlib.sha256(b"auth-restart-verification-manifest").hexdigest()
KEY = hashlib.sha256(b"out-of-band-authentication-key-material").digest()
OTHER_KEY = hashlib.sha256(b"different-out-of-band-authentication-key").digest()


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


def _evidence_kwargs() -> dict[str, str]:
    return {
        "expected_migration_id": "migration-auth-1",
        "expected_session_id": "session-auth-1",
        "expected_target_candidate_id": "target-generated-index",
        "expected_schema_identity": SCHEMA,
        "expected_codec_identity": CODEC,
        "expected_target_artifact_sha256": ARTIFACT,
        "expected_verification_manifest_sha256": MANIFEST,
    }


def _persist_head(tmp_path):
    snapshot = _snapshot(b"alpha")
    inspection = inspect_identified_snapshot(snapshot, expected_schema_identity=SCHEMA, expected_codec_identity=CODEC)
    admission = ProcessTransferAdmission(
        migration_id="migration-auth-1",
        session_id="session-auth-1",
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
    bundle = tmp_path / "accepted.bundle"
    persist_process_transfer_evidence_bundle(
        bundle,
        encode_process_transfer_admission_receipt(admission),
        snapshot,
        **_evidence_kwargs(),
    )
    head = tmp_path / "receiver-head.json"
    advanced = advance_process_transfer_head(
        head,
        bundle,
        authority_id="receiver-a",
        sequence=1,
        expected_previous_head_sha256=GENESIS_HEAD_SHA256,
        **_evidence_kwargs(),
    )
    return head, bundle, advanced


def _tag(
    head_sha256: str,
    *,
    key: bytes = KEY,
    key_id: str = "receiver-key-v1",
    authority_id: str = "receiver-a",
    sequence: int = 1,
) -> str:
    return create_process_transfer_restart_authentication_tag(
        authentication_key=key,
        key_id=key_id,
        authority_id=authority_id,
        sequence=sequence,
        head_sha256=head_sha256,
    )


def _verify(head, bundle, advanced, *, key: bytes = KEY, tag: str | None = None, **overrides):
    kwargs = {
        "authentication_key": key,
        "authentication_key_id": "receiver-key-v1",
        "authentication_tag": tag or _tag(advanced.head_sha256),
        "expected_authority_id": "receiver-a",
        "expected_sequence": 1,
        "expected_head_sha256": advanced.head_sha256,
        **_evidence_kwargs(),
    }
    kwargs.update(overrides)
    return verify_authenticated_persisted_process_transfer_restart(head, bundle, **kwargs)


def test_authenticated_restart_binds_exact_head_and_preserves_no_activation_boundary(tmp_path) -> None:
    head, bundle, advanced = _persist_head(tmp_path)
    head_before = head.read_bytes()
    bundle_before = bundle.read_bytes()

    verified = _verify(head, bundle, advanced)

    assert verified.authentication_verified is True
    assert verified.restart_evidence_verified is True
    assert verified.head_sha256 == advanced.head_sha256
    assert verified.bundle_sha256 == advanced.bundle_sha256
    assert verified.key_id == "receiver-key-v1"
    assert verified.evidence_state == AUTHENTICATED_RESTART_STATE
    assert verified.automatic_control_allowed is False
    assert verified.activation_allowed is False
    assert head.read_bytes() == head_before
    assert bundle.read_bytes() == bundle_before
    assert not head.with_name(head.name + HEAD_LOCK_SUFFIX).exists()
    assert "does not store, provision, rotate, revoke or attest the secret" in TRUTH_BOUNDARY
    assert "provide freshness" in TRUTH_BOUNDARY


def test_authentication_tag_is_deterministic_and_identity_bound() -> None:
    head_sha = hashlib.sha256(b"canonical-head").hexdigest()
    first = _tag(head_sha)
    second = _tag(head_sha)

    assert first == second
    assert first != _tag(head_sha, key_id="receiver-key-v2")
    assert first != _tag(head_sha, authority_id="receiver-b")
    assert first != _tag(head_sha, sequence=2)
    assert first != _tag(hashlib.sha256(b"other-head").hexdigest())


def test_authenticated_restart_rejects_wrong_secret_before_local_restart_verification(tmp_path) -> None:
    head, bundle, advanced = _persist_head(tmp_path)
    tag = _tag(advanced.head_sha256)
    lock = head.with_name(head.name + HEAD_LOCK_SUFFIX)

    with pytest.raises(ValueError, match="authentication tag does not match exact expected head statement"):
        _verify(head, bundle, advanced, key=OTHER_KEY, tag=tag)

    assert not lock.exists()
    assert head.exists()
    assert bundle.exists()


def test_authenticated_restart_rejects_expected_statement_drift(tmp_path) -> None:
    head, bundle, advanced = _persist_head(tmp_path)
    tag = _tag(advanced.head_sha256)

    with pytest.raises(ValueError, match="authentication tag does not match exact expected head statement"):
        _verify(head, bundle, advanced, tag=tag, expected_sequence=2)

    with pytest.raises(ValueError, match="authentication tag does not match exact expected head statement"):
        _verify(head, bundle, advanced, tag=tag, authentication_key_id="receiver-key-v2")


def test_authenticated_restart_rejects_malformed_tag_and_short_secret(tmp_path) -> None:
    head, bundle, advanced = _persist_head(tmp_path)

    with pytest.raises(ValueError, match="lowercase HMAC-SHA256"):
        _verify(head, bundle, advanced, tag="not-a-tag")
    with pytest.raises(ValueError, match="at least 32 bytes"):
        _verify(head, bundle, advanced, key=b"short", tag="0" * 64)


def test_authenticated_restart_does_not_claim_replay_prevention(tmp_path) -> None:
    head, bundle, advanced = _persist_head(tmp_path)
    tag = _tag(advanced.head_sha256)

    first = _verify(head, bundle, advanced, tag=tag)
    second = _verify(head, bundle, advanced, tag=tag)

    assert first.head_sha256 == second.head_sha256 == advanced.head_sha256
    assert first.activation_allowed is second.activation_allowed is False
    assert "anti-replay" in TRUTH_BOUNDARY
