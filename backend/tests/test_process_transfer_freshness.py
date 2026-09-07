from __future__ import annotations

import hashlib

import pytest

import app.process_transfer_auth as process_transfer_auth
from app.process_transfer import ProcessTransferAdmission, inspect_identified_snapshot
from app.process_transfer_auth import (
    FRESH_AUTHENTICATED_RESTART_STATE,
    FRESH_TRUTH_BOUNDARY,
    create_fresh_process_transfer_restart_authentication_tag,
    verify_fresh_authenticated_persisted_process_transfer_restart,
)
from app.process_transfer_head import GENESIS_HEAD_SHA256, advance_process_transfer_head
from app.process_transfer_persistence import persist_process_transfer_evidence_bundle
from app.process_transfer_receipt import encode_process_transfer_admission_receipt


SCHEMA = "morpheus-record-schema-v1:" + hashlib.sha256(b"fresh-restart-schema").hexdigest()
CODEC = "morpheus-fresh-restart-test-codec-v1"
ARTIFACT = hashlib.sha256(b"fresh-restart-target-artifact").hexdigest()
MANIFEST = hashlib.sha256(b"fresh-restart-verification-manifest").hexdigest()
KEY = hashlib.sha256(b"fresh-restart-out-of-band-authentication-key-material").digest()
FRESHNESS_AUTHORITY = "receiver-freshness-service-a"


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
        "expected_migration_id": "migration-fresh-1",
        "expected_session_id": "session-fresh-1",
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
        migration_id="migration-fresh-1",
        session_id="session-fresh-1",
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


def _tag(head_sha256: str, *, freshness_authority_id: str = FRESHNESS_AUTHORITY, freshness_counter: int = 7) -> str:
    return create_fresh_process_transfer_restart_authentication_tag(
        authentication_key=KEY,
        key_id="receiver-key-v1",
        authority_id="receiver-a",
        sequence=1,
        head_sha256=head_sha256,
        freshness_authority_id=freshness_authority_id,
        freshness_counter=freshness_counter,
    )


def _verify(head, bundle, advanced, *, freshness_counter: int = 7, resolver=None, tag: str | None = None, **overrides):
    kwargs = {
        "authentication_key": KEY,
        "authentication_key_id": "receiver-key-v1",
        "authentication_tag": tag or _tag(advanced.head_sha256, freshness_counter=freshness_counter),
        "expected_authority_id": "receiver-a",
        "expected_sequence": 1,
        "expected_head_sha256": advanced.head_sha256,
        "freshness_authority_id": FRESHNESS_AUTHORITY,
        "expected_freshness_counter": freshness_counter,
        "resolve_freshness_counter": resolver or (lambda authority_id: freshness_counter),
        **_evidence_kwargs(),
    }
    kwargs.update(overrides)
    return verify_fresh_authenticated_persisted_process_transfer_restart(head, bundle, **kwargs)


def test_fresh_restart_accepts_exact_external_counter_and_preserves_no_activation_boundary(tmp_path) -> None:
    head, bundle, advanced = _persist_head(tmp_path)
    calls: list[str] = []

    verified = _verify(
        head,
        bundle,
        advanced,
        resolver=lambda authority_id: calls.append(authority_id) or 7,
    )

    assert calls == [FRESHNESS_AUTHORITY]
    assert verified.authentication_verified is True
    assert verified.external_freshness_verified is True
    assert verified.restart_evidence_verified is True
    assert verified.freshness_authority_id == FRESHNESS_AUTHORITY
    assert verified.freshness_counter == 7
    assert verified.head_sha256 == advanced.head_sha256
    assert verified.evidence_state == FRESH_AUTHENTICATED_RESTART_STATE
    assert verified.automatic_control_allowed is False
    assert verified.activation_allowed is False
    assert "does not implement, authenticate, provision, persist, replicate or attest" in FRESH_TRUTH_BOUNDARY


def test_fresh_authentication_tag_is_deterministic_and_binds_external_coordinate() -> None:
    head_sha = hashlib.sha256(b"canonical-fresh-head").hexdigest()

    first = _tag(head_sha)

    assert first == _tag(head_sha)
    assert first != _tag(head_sha, freshness_authority_id="receiver-freshness-service-b")
    assert first != _tag(head_sha, freshness_counter=8)
    assert first != _tag(hashlib.sha256(b"different-head").hexdigest())


def test_external_counter_advance_rejects_replay_before_local_restart_verification(tmp_path, monkeypatch) -> None:
    head, bundle, advanced = _persist_head(tmp_path)
    tag = _tag(advanced.head_sha256, freshness_counter=7)
    replay_calls = 0

    def forbidden_restart(*args, **kwargs):
        nonlocal replay_calls
        replay_calls += 1
        raise AssertionError("local restart replay must not run for stale freshness")

    monkeypatch.setattr(process_transfer_auth, "verify_persisted_process_transfer_restart", forbidden_restart)

    with pytest.raises(ValueError, match="authenticated freshness counter is stale"):
        _verify(head, bundle, advanced, freshness_counter=7, resolver=lambda authority_id: 8, tag=tag)

    assert replay_calls == 0


def test_expected_counter_ahead_of_external_authority_fails_closed(tmp_path, monkeypatch) -> None:
    head, bundle, advanced = _persist_head(tmp_path)
    replay_calls = 0

    def forbidden_restart(*args, **kwargs):
        nonlocal replay_calls
        replay_calls += 1
        raise AssertionError("local restart replay must not run for inconsistent freshness")

    monkeypatch.setattr(process_transfer_auth, "verify_persisted_process_transfer_restart", forbidden_restart)

    with pytest.raises(ValueError, match="authenticated freshness counter is ahead of authority"):
        _verify(head, bundle, advanced, freshness_counter=8, resolver=lambda authority_id: 7)

    assert replay_calls == 0


def test_freshness_authority_lookup_errors_and_invalid_values_fail_closed(tmp_path) -> None:
    head, bundle, advanced = _persist_head(tmp_path)

    def unavailable(authority_id: str) -> int:
        raise RuntimeError("authority unavailable")

    with pytest.raises(ValueError, match="external freshness authority lookup failed"):
        _verify(head, bundle, advanced, resolver=unavailable)

    with pytest.raises(ValueError, match="observed_freshness_counter must be a non-negative integer"):
        _verify(head, bundle, advanced, resolver=lambda authority_id: True)

    with pytest.raises(ValueError, match="observed_freshness_counter must be a non-negative integer"):
        _verify(head, bundle, advanced, resolver=lambda authority_id: -1)


def test_authentication_drift_rejected_before_freshness_lookup(tmp_path) -> None:
    head, bundle, advanced = _persist_head(tmp_path)
    tag = _tag(advanced.head_sha256, freshness_counter=7)
    calls = 0

    def resolver(authority_id: str) -> int:
        nonlocal calls
        calls += 1
        return 8

    with pytest.raises(ValueError, match="fresh restart authentication tag does not match exact expected statement"):
        _verify(
            head,
            bundle,
            advanced,
            tag=tag,
            freshness_counter=8,
            resolver=resolver,
        )

    assert calls == 0


def test_external_freshness_gate_does_not_claim_authority_correctness_or_global_freshness() -> None:
    assert "does not prove resolver liveness, correctness, atomicity or compromise resistance" in FRESH_TRUTH_BOUNDARY
    assert "does not provide global freshness" in FRESH_TRUTH_BOUNDARY
    assert "activation/automatic-control authority" in FRESH_TRUTH_BOUNDARY


@pytest.mark.parametrize("invalid_counter", [None, "7", 7.0, b"7", True, False, -1])
def test_freshness_resolver_rejects_non_integer_counter_types_before_restart_replay(
    tmp_path, monkeypatch, invalid_counter
) -> None:
    head, bundle, advanced = _persist_head(tmp_path)
    replay_calls = 0

    def forbidden_restart(*args, **kwargs):
        nonlocal replay_calls
        replay_calls += 1
        raise AssertionError("local restart replay must not run for malformed freshness evidence")

    monkeypatch.setattr(process_transfer_auth, "verify_persisted_process_transfer_restart", forbidden_restart)

    with pytest.raises(ValueError, match="observed_freshness_counter must be a non-negative integer"):
        _verify(head, bundle, advanced, resolver=lambda authority_id: invalid_counter)

    assert replay_calls == 0