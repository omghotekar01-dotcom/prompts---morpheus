import hashlib
from dataclasses import replace

import pytest

from app.recovery_p105 import EVIDENCE_STATE as P105_EVIDENCE_STATE, RecoveryP104ReplayEvidence
from app.recovery_p106 import EVIDENCE_STATE, TRUTH_BOUNDARY, store_p105_replay_identity


INT_FIELDS = {
    "sequence",
    "binding_receipt_payload_size_bytes",
    "retained_identity_payload_size_bytes",
    "replay_binding_receipt_payload_size_bytes",
    "retained_replay_identity_payload_size_bytes",
    "replay_retained_identity_binding_receipt_payload_size_bytes",
    "retained_replay_receipt_identity_payload_size_bytes",
    "replay_retained_receipt_identity_binding_receipt_payload_size_bytes",
    "retained_replayed_receipt_identity_payload_size_bytes",
    "replayed_receipt_retained_identity_binding_receipt_payload_size_bytes",
    "retained_p101_record_payload_size_bytes",
    "p104_receipt_payload_size_bytes",
}
FIELDS = (
    "sequence", "lineage_sha256", "binding_receipt_payload_sha256", "binding_receipt_payload_size_bytes",
    "receipt_identity_binding_sha256", "retained_identity_payload_sha256", "retained_identity_payload_size_bytes",
    "replay_stored_identity_binding_sha256", "replay_binding_receipt_payload_sha256", "replay_binding_receipt_payload_size_bytes",
    "retained_replay_identity_payload_sha256", "retained_replay_identity_payload_size_bytes", "replay_retained_identity_binding_sha256",
    "replay_retained_identity_binding_receipt_payload_sha256", "replay_retained_identity_binding_receipt_payload_size_bytes",
    "retained_replay_receipt_identity_payload_sha256", "retained_replay_receipt_identity_payload_size_bytes",
    "replay_retained_receipt_identity_binding_sha256", "replay_retained_receipt_identity_binding_receipt_payload_sha256",
    "replay_retained_receipt_identity_binding_receipt_payload_size_bytes", "retained_replayed_receipt_identity_payload_sha256",
    "retained_replayed_receipt_identity_payload_size_bytes", "replayed_receipt_retained_identity_binding_sha256",
    "replayed_receipt_retained_identity_binding_receipt_payload_sha256", "replayed_receipt_retained_identity_binding_receipt_payload_size_bytes",
    "retained_p101_record_payload_sha256", "retained_p101_record_payload_size_bytes", "p100_p102_composition_binding_sha256",
    "p104_receipt_payload_sha256", "p104_receipt_payload_size_bytes",
)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _evidence() -> RecoveryP104ReplayEvidence:
    values = {field: (index if field in INT_FIELDS else _sha(field)) for index, field in enumerate(FIELDS, 1)}
    return RecoveryP104ReplayEvidence(
        **values,
        expected_payload_identity_verified=True,
        canonical_receipt_verified=True,
        dependency_state_verified=True,
        p100_p102_composition_binding_recomputed_verified=True,
        p103_evidence_state="test-p103-state",
    )


def test_stores_canonical_verified_p105_identity(tmp_path):
    destination = tmp_path / "nested" / "p105.identity.json"
    stored = store_p105_replay_identity(_evidence(), destination_path=destination)
    payload = destination.read_bytes()
    assert stored.stored_payload_sha256 == hashlib.sha256(payload).hexdigest()
    assert stored.stored_payload_size_bytes == len(payload)
    assert stored.destination_path == str(destination)
    assert stored.p105_evidence_state_verified is True
    assert stored.p105_verification_flags_verified is True
    assert stored.exact_readback_verified is True
    assert stored.evidence_state == EVIDENCE_STATE
    assert stored.automatic_control_allowed is False
    assert not list(destination.parent.glob(f".{destination.name}.*.tmp"))


def test_storage_is_deterministic_and_replaces_existing_file(tmp_path):
    destination = tmp_path / "identity.json"
    destination.write_text("old")
    first = store_p105_replay_identity(_evidence(), destination_path=destination)
    first_payload = destination.read_bytes()
    second = store_p105_replay_identity(_evidence(), destination_path=destination)
    assert destination.read_bytes() == first_payload
    assert second.stored_payload_sha256 == first.stored_payload_sha256
    assert second.stored_payload_size_bytes == first.stored_payload_size_bytes


@pytest.mark.parametrize(
    "flag",
    ["expected_payload_identity_verified", "canonical_receipt_verified", "dependency_state_verified", "p100_p102_composition_binding_recomputed_verified"],
)
def test_rejects_weakened_p105_verification_contract(tmp_path, flag):
    with pytest.raises(ValueError, match="verification flags are incomplete"):
        store_p105_replay_identity(replace(_evidence(), **{flag: False}), destination_path=tmp_path / "x")


def test_rejects_state_drift_and_authority_escalation(tmp_path):
    with pytest.raises(ValueError, match="state is incompatible"):
        store_p105_replay_identity(replace(_evidence(), evidence_state=P105_EVIDENCE_STATE + "_DRIFT"), destination_path=tmp_path / "x")
    with pytest.raises(ValueError, match="must not grant automatic-control authority"):
        store_p105_replay_identity(replace(_evidence(), automatic_control_allowed=True), destination_path=tmp_path / "x")


@pytest.mark.parametrize("invalid", [True, 0, -1])
def test_rejects_invalid_positive_integer_identity(tmp_path, invalid):
    with pytest.raises(ValueError, match="positive integer"):
        store_p105_replay_identity(replace(_evidence(), sequence=invalid), destination_path=tmp_path / "x")


def test_rejects_malformed_sha_identity(tmp_path):
    with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
        store_p105_replay_identity(replace(_evidence(), lineage_sha256="A" * 64), destination_path=tmp_path / "x")


@pytest.mark.parametrize("field", FIELDS)
def test_stored_identity_is_sensitive_to_every_retained_semantic_field(tmp_path, field):
    original = _evidence()
    changed_value = getattr(original, field) + 1 if field in INT_FIELDS else _sha("changed-" + field)
    first = store_p105_replay_identity(original, destination_path=tmp_path / "a")
    second = store_p105_replay_identity(replace(original, **{field: changed_value}), destination_path=tmp_path / "b")
    assert first.stored_payload_sha256 != second.stored_payload_sha256


def test_rejects_incompatible_evidence_type(tmp_path):
    with pytest.raises(ValueError, match="incompatible type"):
        store_p105_replay_identity(object(), destination_path=tmp_path / "x")


def test_truth_boundary_remains_explicitly_non_authoritative(tmp_path):
    rendered = store_p105_replay_identity(_evidence(), destination_path=tmp_path / "x").as_dict()
    assert rendered["automatic_control_allowed"] is False
    assert rendered["truth_boundary"] == TRUTH_BOUNDARY
    for phrase in (
        "does not authenticate", "freshness/latest/global/monotonic", "prevent rollback/replay",
        "authorize startup or mutation", "production readiness", "benchmark evidence", "novelty evidence",
    ):
        assert phrase in TRUTH_BOUNDARY
