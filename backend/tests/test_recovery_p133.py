import hashlib
import json
from dataclasses import replace

import pytest

from app.recovery_p128 import EVIDENCE_STATE as P128_EVIDENCE_STATE
from app.recovery_p130 import EVIDENCE_STATE as P130_EVIDENCE_STATE, RecoveryP129ReceiptVerificationEvidence
from app.recovery_p131 import _FIELDS
from app.recovery_p132 import EVIDENCE_STATE as P132_EVIDENCE_STATE, RecoveryP130ReceiptIdentityVerificationEvidence
from app.recovery_p133 import EVIDENCE_STATE, TRUTH_BOUNDARY, bind_p130_replay_to_p132_retained_identity


FIELDS = tuple(field for field, _ in _FIELDS)
INT_FIELDS = {field for field, kind in _FIELDS if kind == "int"}
P130_FLAGS = (
    "exact_size_verified",
    "exact_sha256_verified",
    "strict_schema_verified",
    "canonical_encoding_verified",
    "retained_identity_verified",
    "p128_evidence_state_verified",
    "p129_contract_verified",
)
P132_FLAGS = (
    "exact_size_verified",
    "exact_sha256_verified",
    "strict_schema_verified",
    "canonical_encoding_verified",
    "retained_identity_verified",
    "p130_evidence_state_verified",
)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _receipt(**changes):
    values = dict(
        receipt_payload_sha256=_sha("p129-receipt"),
        receipt_payload_size_bytes=321,
        exact_size_verified=True,
        exact_sha256_verified=True,
        strict_schema_verified=True,
        canonical_encoding_verified=True,
        retained_identity_verified=True,
        p128_evidence_state_verified=True,
        p129_contract_verified=True,
    )
    values.update(changes)
    return RecoveryP129ReceiptVerificationEvidence(**values)


def _retained(**changes):
    values = dict(
        receipt_payload_sha256=_sha("p129-receipt"),
        receipt_payload_size_bytes=321,
        stored_payload_sha256=_sha("p131-record"),
        stored_payload_size_bytes=207,
        source_path="p130.identity.json",
        exact_size_verified=True,
        exact_sha256_verified=True,
        strict_schema_verified=True,
        canonical_encoding_verified=True,
        retained_identity_verified=True,
        p130_evidence_state_verified=True,
    )
    values.update(changes)
    return RecoveryP130ReceiptIdentityVerificationEvidence(**values)


def test_p133_deterministically_binds_matching_p130_and_p132_evidence() -> None:
    receipt = _receipt()
    retained = _retained()
    first = bind_p130_replay_to_p132_retained_identity(receipt, retained)
    second = bind_p130_replay_to_p132_retained_identity(receipt, retained)

    assert first == second
    assert first.receipt_payload_sha256 == receipt.receipt_payload_sha256
    assert first.receipt_payload_size_bytes == receipt.receipt_payload_size_bytes
    assert first.retained_p131_record_payload_sha256 == retained.stored_payload_sha256
    assert first.retained_p131_record_payload_size_bytes == retained.stored_payload_size_bytes
    assert len(first.p130_p132_composition_binding_sha256) == 64
    assert first.p130_contract_verified is True
    assert first.p132_contract_verified is True
    assert first.cross_evidence_identity_verified is True
    assert first.evidence_state == EVIDENCE_STATE
    assert first.automatic_control_allowed is False


def test_p133_binding_matches_exact_canonical_contract_payload() -> None:
    receipt = _receipt()
    retained = _retained()
    evidence = bind_p130_replay_to_p132_retained_identity(receipt, retained)

    canonical_payload = {
        **{field: getattr(receipt, field) for field in FIELDS},
        "retained_p131_record_payload_sha256": retained.stored_payload_sha256,
        "retained_p131_record_payload_size_bytes": retained.stored_payload_size_bytes,
        "p128_evidence_state": P128_EVIDENCE_STATE,
        "p130_evidence_state": P130_EVIDENCE_STATE,
        "p132_evidence_state": P132_EVIDENCE_STATE,
    }
    expected = hashlib.sha256(
        json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()

    assert evidence.p130_p132_composition_binding_sha256 == expected


@pytest.mark.parametrize("field", FIELDS)
def test_p133_rejects_each_shared_identity_mismatch(field) -> None:
    retained = _retained()
    replacement = retained.receipt_payload_size_bytes + 1 if field in INT_FIELDS else _sha("drift-" + field)
    retained = replace(retained, **{field: replacement})
    with pytest.raises(ValueError, match=f"disagrees on {field}"):
        bind_p130_replay_to_p132_retained_identity(_receipt(), retained)


@pytest.mark.parametrize("flag", P130_FLAGS)
def test_p133_rejects_each_weakened_p130_verification_flag(flag) -> None:
    with pytest.raises(ValueError, match="P130 verification contract is incomplete"):
        bind_p130_replay_to_p132_retained_identity(replace(_receipt(), **{flag: False}), _retained())


@pytest.mark.parametrize("flag", P132_FLAGS)
def test_p133_rejects_each_weakened_p132_verification_flag(flag) -> None:
    with pytest.raises(ValueError, match="P132 verification contract is incomplete"):
        bind_p130_replay_to_p132_retained_identity(_receipt(), replace(_retained(), **{flag: False}))


def test_p133_rejects_dependency_state_and_authority_drift() -> None:
    with pytest.raises(ValueError, match="P130 evidence state is incompatible"):
        bind_p130_replay_to_p132_retained_identity(replace(_receipt(), evidence_state=P130_EVIDENCE_STATE + "_DRIFT"), _retained())
    with pytest.raises(ValueError, match="P132 evidence state is incompatible"):
        bind_p130_replay_to_p132_retained_identity(_receipt(), replace(_retained(), evidence_state=P132_EVIDENCE_STATE + "_DRIFT"))
    with pytest.raises(ValueError, match="P130 evidence must not grant"):
        bind_p130_replay_to_p132_retained_identity(replace(_receipt(), automatic_control_allowed=True), _retained())
    with pytest.raises(ValueError, match="P132 evidence must not grant"):
        bind_p130_replay_to_p132_retained_identity(_receipt(), replace(_retained(), automatic_control_allowed=True))


@pytest.mark.parametrize(
    ("side", "field", "value", "message"),
    [
        ("receipt", "receipt_payload_size_bytes", True, "positive integer"),
        ("receipt", "receipt_payload_sha256", "A" * 64, "64 lowercase hexadecimal"),
        ("retained", "receipt_payload_size_bytes", 0, "positive integer"),
        ("retained", "receipt_payload_sha256", "0" * 63, "64 lowercase hexadecimal"),
        ("retained", "stored_payload_size_bytes", True, "positive integer"),
        ("retained", "stored_payload_sha256", "A" * 64, "64 lowercase hexadecimal"),
    ],
)
def test_p133_rejects_malformed_shared_or_retained_identity(side, field, value, message) -> None:
    receipt = _receipt()
    retained = _retained()
    if side == "receipt":
        receipt = replace(receipt, **{field: value})
    else:
        retained = replace(retained, **{field: value})
    with pytest.raises(ValueError, match=message):
        bind_p130_replay_to_p132_retained_identity(receipt, retained)


def test_p133_binding_is_sensitive_to_selected_retained_record_identity() -> None:
    receipt = _receipt()
    first = bind_p130_replay_to_p132_retained_identity(receipt, _retained())
    changed_sha = bind_p130_replay_to_p132_retained_identity(receipt, _retained(stored_payload_sha256=_sha("other-record")))
    changed_size = bind_p130_replay_to_p132_retained_identity(receipt, _retained(stored_payload_size_bytes=208))

    assert first.p130_p132_composition_binding_sha256 != changed_sha.p130_p132_composition_binding_sha256
    assert first.p130_p132_composition_binding_sha256 != changed_size.p130_p132_composition_binding_sha256


def test_p133_rejects_incompatible_types() -> None:
    with pytest.raises(ValueError, match="P130 canonical P129 replay evidence has an incompatible type"):
        bind_p130_replay_to_p132_retained_identity(object(), _retained())
    with pytest.raises(ValueError, match="P132 retained P131 replay evidence has an incompatible type"):
        bind_p130_replay_to_p132_retained_identity(_receipt(), object())


def test_p133_truth_boundary_is_explicitly_read_only_and_non_authoritative() -> None:
    lowered = TRUTH_BOUNDARY.lower()
    assert "read-only" in lowered
    assert "does not authenticate" in lowered
    assert "freshness" in lowered
    assert "rollback" in lowered
    assert "authorize startup" in lowered
    assert "production readiness" in lowered
    assert "benchmark evidence" in lowered
    assert "novelty evidence" in lowered
    assert "automatic-control authority" in lowered
