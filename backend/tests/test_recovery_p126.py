import hashlib
from dataclasses import replace

import pytest

from app.recovery_p123 import EVIDENCE_STATE as P123_EVIDENCE_STATE
from app.recovery_p125 import (
    EVIDENCE_STATE as P125_EVIDENCE_STATE,
    RecoveryP124ReplayEvidence,
    _FIELDS as P125_RECEIPT_FIELDS,
)
from app.recovery_p126 import EVIDENCE_STATE, TRUTH_BOUNDARY, _FIELDS, store_p125_replay_identity


INT_FIELDS = {field for field, kind in _FIELDS if kind == "int"}
FIELDS = tuple(field for field, _ in _FIELDS)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _evidence() -> RecoveryP124ReplayEvidence:
    values = {
        field: (index if field in INT_FIELDS else _sha(field))
        for index, field in enumerate(FIELDS, 1)
    }
    return RecoveryP124ReplayEvidence(
        **values,
        expected_payload_identity_verified=True,
        canonical_receipt_verified=True,
        dependency_state_verified=True,
        p120_p122_composition_binding_recomputed_verified=True,
        p123_evidence_state=P123_EVIDENCE_STATE,
    )


def test_p126_field_contract_extends_exact_p125_serialized_identity():
    assert _FIELDS == (
        *P125_RECEIPT_FIELDS,
        ("p124_receipt_payload_sha256", "sha"),
        ("p124_receipt_payload_size_bytes", "int"),
    )


def test_stores_canonical_verified_p125_identity(tmp_path):
    destination = tmp_path / "nested" / "p125.identity.json"
    stored = store_p125_replay_identity(_evidence(), destination_path=destination)
    payload = destination.read_bytes()
    assert stored.stored_payload_sha256 == hashlib.sha256(payload).hexdigest()
    assert stored.stored_payload_size_bytes == len(payload)
    assert stored.destination_path == str(destination)
    assert stored.p125_evidence_state_verified is True
    assert stored.p125_verification_flags_verified is True
    assert stored.exact_readback_verified is True
    assert stored.evidence_state == EVIDENCE_STATE
    assert stored.automatic_control_allowed is False
    assert not list(destination.parent.glob(f".{destination.name}.*.tmp"))


def test_storage_is_deterministic_and_replaces_existing_file(tmp_path):
    destination = tmp_path / "identity.json"
    destination.write_text("old")
    first = store_p125_replay_identity(_evidence(), destination_path=destination)
    first_payload = destination.read_bytes()
    second = store_p125_replay_identity(_evidence(), destination_path=destination)
    assert destination.read_bytes() == first_payload
    assert second.stored_payload_sha256 == first.stored_payload_sha256
    assert second.stored_payload_size_bytes == first.stored_payload_size_bytes


@pytest.mark.parametrize(
    "flag",
    [
        "expected_payload_identity_verified",
        "canonical_receipt_verified",
        "dependency_state_verified",
        "p120_p122_composition_binding_recomputed_verified",
    ],
)
def test_rejects_weakened_p125_verification_contract(tmp_path, flag):
    with pytest.raises(ValueError, match="verification flags are incomplete"):
        store_p125_replay_identity(
            replace(_evidence(), **{flag: False}),
            destination_path=tmp_path / "x",
        )


def test_rejects_state_drift_and_authority_escalation(tmp_path):
    with pytest.raises(ValueError, match="state is incompatible"):
        store_p125_replay_identity(
            replace(_evidence(), evidence_state=P125_EVIDENCE_STATE + "_DRIFT"),
            destination_path=tmp_path / "x",
        )
    with pytest.raises(ValueError, match="must not grant automatic-control authority"):
        store_p125_replay_identity(
            replace(_evidence(), automatic_control_allowed=True),
            destination_path=tmp_path / "x",
        )


@pytest.mark.parametrize("invalid", [True, 0, -1])
@pytest.mark.parametrize("field", sorted(INT_FIELDS))
def test_rejects_invalid_positive_integer_identity(tmp_path, field, invalid):
    with pytest.raises(ValueError, match="positive integer"):
        store_p125_replay_identity(
            replace(_evidence(), **{field: invalid}),
            destination_path=tmp_path / "x",
        )


@pytest.mark.parametrize("field", [field for field in FIELDS if field not in INT_FIELDS])
def test_rejects_malformed_sha_identity(tmp_path, field):
    with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
        store_p125_replay_identity(
            replace(_evidence(), **{field: "A" * 64}),
            destination_path=tmp_path / "x",
        )


@pytest.mark.parametrize("field", FIELDS)
def test_stored_identity_is_sensitive_to_every_retained_semantic_field(tmp_path, field):
    original = _evidence()
    changed_value = (
        getattr(original, field) + 1
        if field in INT_FIELDS
        else _sha("changed-" + field)
    )
    first = store_p125_replay_identity(original, destination_path=tmp_path / "a")
    second = store_p125_replay_identity(
        replace(original, **{field: changed_value}),
        destination_path=tmp_path / "b",
    )
    assert first.stored_payload_sha256 != second.stored_payload_sha256


def test_rejects_incompatible_evidence_type(tmp_path):
    with pytest.raises(ValueError, match="incompatible type"):
        store_p125_replay_identity(object(), destination_path=tmp_path / "x")


def test_truth_boundary_remains_explicitly_non_authoritative(tmp_path):
    rendered = store_p125_replay_identity(
        _evidence(), destination_path=tmp_path / "x"
    ).as_dict()
    assert rendered["automatic_control_allowed"] is False
    assert rendered["truth_boundary"] == TRUTH_BOUNDARY
    for phrase in (
        "does not authenticate",
        "freshness/latest/global/monotonic",
        "prevent rollback/replay",
        "authorize startup or mutation",
        "production readiness",
        "benchmark evidence",
        "novelty evidence",
    ):
        assert phrase in TRUTH_BOUNDARY
