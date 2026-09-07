from __future__ import annotations

import hashlib

import pytest

import app.process_transfer_fencing as process_transfer_fencing
from app.process_transfer import ProcessTransferAdmission, inspect_identified_snapshot
from app.process_transfer_fencing import (
    FENCED_AUTHENTICATED_RESTART_STATE,
    FENCING_TRUTH_BOUNDARY,
    create_fenced_process_transfer_restart_authentication_tag,
    verify_fenced_authenticated_persisted_process_transfer_restart,
)
from app.process_transfer_head import GENESIS_HEAD_SHA256, advance_process_transfer_head
from app.process_transfer_persistence import persist_process_transfer_evidence_bundle
from app.process_transfer_receipt import encode_process_transfer_admission_receipt


SCHEMA = "morpheus-record-schema-v1:" + hashlib.sha256(b"fenced-restart-schema").hexdigest()
CODEC = "morpheus-fenced-restart-test-codec-v1"
ARTIFACT = hashlib.sha256(b"fenced-restart-target-artifact").hexdigest()
MANIFEST = hashlib.sha256(b"fenced-restart-verification-manifest").hexdigest()
KEY = hashlib.sha256(b"fenced-restart-out-of-band-authentication-key-material").digest()
FENCING_AUTHORITY = "receiver-fencing-service-a"


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
        "expected_migration_id": "migration-fenced-1",
        "expected_session_id": "session-fenced-1",
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
        migration_id="migration-fenced-1",
        session_id="session-fenced-1",
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


def _tag(head_sha256: str, *, previous: int = 11, requested: int = 12) -> str:
    return create_fenced_process_transfer_restart_authentication_tag(
        authentication_key=KEY,
        key_id="receiver-key-v1",
        authority_id="receiver-a",
        sequence=1,
        head_sha256=head_sha256,
        fencing_authority_id=FENCING_AUTHORITY,
        previous_fencing_counter=previous,
        fencing_counter=requested,
    )


def _verify(head, bundle, advanced, *, previous: int = 11, requested: int = 12, claim=None, tag=None, **overrides):
    kwargs = {
        "authentication_key": KEY,
        "authentication_key_id": "receiver-key-v1",
        "authentication_tag": tag or _tag(advanced.head_sha256, previous=previous, requested=requested),
        "expected_authority_id": "receiver-a",
        "expected_sequence": 1,
        "expected_head_sha256": advanced.head_sha256,
        "fencing_authority_id": FENCING_AUTHORITY,
        "expected_previous_fencing_counter": previous,
        "requested_fencing_counter": requested,
        "claim_fencing_counter": claim or (lambda authority_id, expected, desired: desired),
        **_evidence_kwargs(),
    }
    kwargs.update(overrides)
    return verify_fenced_authenticated_persisted_process_transfer_restart(head, bundle, **kwargs)


def test_fenced_restart_claims_exact_next_generation_and_preserves_no_activation_boundary(tmp_path) -> None:
    head, bundle, advanced = _persist_head(tmp_path)
    calls: list[tuple[str, int, int]] = []

    verified = _verify(
        head,
        bundle,
        advanced,
        claim=lambda authority_id, expected, desired: calls.append((authority_id, expected, desired)) or desired,
    )

    assert calls == [(FENCING_AUTHORITY, 11, 12)]
    assert verified.authentication_verified is True
    assert verified.external_fencing_claim_verified is True
    assert verified.restart_evidence_verified is True
    assert verified.previous_fencing_counter == 11
    assert verified.fencing_counter == 12
    assert verified.head_sha256 == advanced.head_sha256
    assert verified.evidence_state == FENCED_AUTHENTICATED_RESTART_STATE
    assert verified.automatic_control_allowed is False
    assert verified.activation_allowed is False
    assert verified.traffic_switching_allowed is False


def test_fencing_tag_is_deterministic_and_binds_compare_and_advance_coordinates() -> None:
    head_sha = hashlib.sha256(b"canonical-fenced-head").hexdigest()
    first = _tag(head_sha)

    assert first == _tag(head_sha)
    assert first != _tag(head_sha, previous=12, requested=13)
    assert first != _tag(hashlib.sha256(b"different-head").hexdigest())


def test_non_contiguous_requested_fencing_generation_is_rejected_before_external_claim(tmp_path) -> None:
    head, bundle, advanced = _persist_head(tmp_path)
    calls = 0

    def forbidden_claim(*args):
        nonlocal calls
        calls += 1
        raise AssertionError("external claim must not run")

    with pytest.raises(ValueError, match="requested_fencing_counter must be exactly"):
        _verify(head, bundle, advanced, previous=11, requested=13, claim=forbidden_claim, tag="0" * 64)

    assert calls == 0


def test_authentication_drift_is_rejected_before_external_fencing_claim(tmp_path) -> None:
    head, bundle, advanced = _persist_head(tmp_path)
    tag = _tag(advanced.head_sha256, previous=11, requested=12)
    calls = 0

    def forbidden_claim(*args):
        nonlocal calls
        calls += 1
        return 13

    with pytest.raises(ValueError, match="fencing authentication tag does not match exact expected statement"):
        _verify(head, bundle, advanced, previous=12, requested=13, claim=forbidden_claim, tag=tag)

    assert calls == 0


def test_external_compare_and_advance_failure_prevents_local_restart_replay(tmp_path, monkeypatch) -> None:
    head, bundle, advanced = _persist_head(tmp_path)
    replay_calls = 0

    def forbidden_restart(*args, **kwargs):
        nonlocal replay_calls
        replay_calls += 1
        raise AssertionError("restart replay must not run without an external fencing claim")

    monkeypatch.setattr(process_transfer_fencing, "verify_persisted_process_transfer_restart", forbidden_restart)

    def stale_compare(authority_id: str, expected: int, desired: int) -> int:
        raise RuntimeError("compare failed: authority already advanced")

    with pytest.raises(ValueError, match="external fencing authority compare-and-advance failed"):
        _verify(head, bundle, advanced, claim=stale_compare)

    assert replay_calls == 0


@pytest.mark.parametrize("invalid", [None, "12", 12.0, b"12", True, False, -1])
def test_external_claim_rejects_malformed_return_values_before_restart_replay(tmp_path, monkeypatch, invalid) -> None:
    head, bundle, advanced = _persist_head(tmp_path)
    replay_calls = 0

    def forbidden_restart(*args, **kwargs):
        nonlocal replay_calls
        replay_calls += 1
        raise AssertionError("restart replay must not run for malformed fencing evidence")

    monkeypatch.setattr(process_transfer_fencing, "verify_persisted_process_transfer_restart", forbidden_restart)

    with pytest.raises(ValueError, match="claimed_fencing_counter must be a non-negative integer"):
        _verify(head, bundle, advanced, claim=lambda authority_id, expected, desired: invalid)

    assert replay_calls == 0


def test_external_claim_must_return_exact_requested_generation_before_restart_replay(tmp_path, monkeypatch) -> None:
    head, bundle, advanced = _persist_head(tmp_path)
    replay_calls = 0

    def forbidden_restart(*args, **kwargs):
        nonlocal replay_calls
        replay_calls += 1
        raise AssertionError("restart replay must not run after an inconsistent fencing response")

    monkeypatch.setattr(process_transfer_fencing, "verify_persisted_process_transfer_restart", forbidden_restart)

    with pytest.raises(ValueError, match="did not return the exact requested next counter"):
        _verify(head, bundle, advanced, claim=lambda authority_id, expected, desired: desired + 1)

    assert replay_calls == 0


def test_consumed_external_generation_is_not_rolled_back_when_local_restart_replay_fails(tmp_path) -> None:
    head, bundle, advanced = _persist_head(tmp_path)
    authority_state = {FENCING_AUTHORITY: 11}

    def compare_and_advance(authority_id: str, expected: int, desired: int) -> int:
        if authority_state[authority_id] != expected:
            raise RuntimeError("stale expected counter")
        authority_state[authority_id] = desired
        return desired

    with pytest.raises(ValueError):
        _verify(
            head,
            bundle,
            advanced,
            claim=compare_and_advance,
            expected_session_id="wrong-session-after-fence-claim",
        )

    assert authority_state[FENCING_AUTHORITY] == 12


def test_fencing_truth_boundary_does_not_claim_external_authority_or_cutover_correctness() -> None:
    assert "does not implement, authenticate, persist, replicate, attest or prove atomicity" in FENCING_TRUTH_BOUNDARY
    assert "multi-receiver correctness" in FENCING_TRUTH_BOUNDARY
    assert "not activation, automatic-control, traffic-switching" in FENCING_TRUTH_BOUNDARY
