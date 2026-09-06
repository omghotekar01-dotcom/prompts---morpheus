import hashlib
import json
from dataclasses import replace

import pytest

from app.recovery_p130 import EVIDENCE_STATE as P130_EVIDENCE_STATE, RecoveryP129ReceiptVerificationEvidence
from app.recovery_p131 import EVIDENCE_STATE as P131_EVIDENCE_STATE, _FIELDS, store_p130_receipt_identity
from app.recovery_p132 import EVIDENCE_STATE, TRUTH_BOUNDARY, verify_stored_p130_receipt_identity


INT_FIELDS = {field for field, kind in _FIELDS if kind == "int"}
FIELDS = tuple(field for field, _ in _FIELDS)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _p130_evidence() -> RecoveryP129ReceiptVerificationEvidence:
    return RecoveryP129ReceiptVerificationEvidence(
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


def _store(tmp_path):
    return store_p130_receipt_identity(
        _p130_evidence(), destination_path=tmp_path / "p130.identity.json"
    )


def _rewrite_and_rebind(store, payload: bytes):
    path = store.destination_path
    with open(path, "wb") as handle:
        handle.write(payload)
    return replace(
        store,
        stored_payload_sha256=hashlib.sha256(payload).hexdigest(),
        stored_payload_size_bytes=len(payload),
    )


def _canonical(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def test_p132_independently_verifies_exact_stored_p131_identity(tmp_path) -> None:
    store = _store(tmp_path)
    verified = verify_stored_p130_receipt_identity(store)

    for field in FIELDS:
        assert getattr(verified, field) == getattr(store, field)
    assert verified.stored_payload_sha256 == store.stored_payload_sha256
    assert verified.stored_payload_size_bytes == store.stored_payload_size_bytes
    assert verified.source_path == store.destination_path
    assert verified.exact_size_verified is True
    assert verified.exact_sha256_verified is True
    assert verified.strict_schema_verified is True
    assert verified.canonical_encoding_verified is True
    assert verified.retained_identity_verified is True
    assert verified.p130_evidence_state_verified is True
    assert verified.evidence_state == EVIDENCE_STATE
    assert verified.automatic_control_allowed is False


def test_p132_rejects_missing_or_tampered_stored_bytes(tmp_path) -> None:
    store = _store(tmp_path)
    with open(store.destination_path, "ab") as handle:
        handle.write(b"x")
    with pytest.raises(ValueError, match="size mismatch"):
        verify_stored_p130_receipt_identity(store)

    store = _store(tmp_path)
    payload = bytearray(open(store.destination_path, "rb").read())
    payload[-2] = ord("0") if payload[-2] != ord("0") else ord("1")
    with open(store.destination_path, "wb") as handle:
        handle.write(payload)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_stored_p130_receipt_identity(store)

    store = _store(tmp_path)
    missing = tmp_path / "missing.identity.json"
    with pytest.raises(ValueError, match="could not be read"):
        verify_stored_p130_receipt_identity(store, source_path=missing)


def test_p132_rejects_noncanonical_json_with_rebound_outer_identity(tmp_path) -> None:
    store = _store(tmp_path)
    payload = json.loads(open(store.destination_path, encoding="utf-8").read())
    pretty = json.dumps(payload, sort_keys=True, indent=2).encode()
    rebound = _rewrite_and_rebind(store, pretty)
    with pytest.raises(ValueError, match="not canonically encoded"):
        verify_stored_p130_receipt_identity(rebound)


def test_p132_rejects_schema_and_embedded_state_drift_with_rebound_identity(tmp_path) -> None:
    store = _store(tmp_path)
    payload = json.loads(open(store.destination_path, encoding="utf-8").read())
    payload["unexpected"] = "field"
    rebound = _rewrite_and_rebind(store, _canonical(payload))
    with pytest.raises(ValueError, match="schema mismatch"):
        verify_stored_p130_receipt_identity(rebound)

    store = _store(tmp_path)
    payload = json.loads(open(store.destination_path, encoding="utf-8").read())
    payload["p130_evidence_state"] = P130_EVIDENCE_STATE + "_DRIFT"
    rebound = _rewrite_and_rebind(store, _canonical(payload))
    with pytest.raises(ValueError, match="incompatible P130 evidence state"):
        verify_stored_p130_receipt_identity(rebound)


@pytest.mark.parametrize("field", FIELDS)
def test_p132_rejects_each_retained_field_drift_with_rebound_identity(tmp_path, field) -> None:
    store = _store(tmp_path)
    payload = json.loads(open(store.destination_path, encoding="utf-8").read())
    payload[field] = payload[field] + 1 if field in INT_FIELDS else _sha("drift-" + field)
    rebound = _rewrite_and_rebind(store, _canonical(payload))
    with pytest.raises(ValueError, match=f"field mismatch: {field}"):
        verify_stored_p130_receipt_identity(rebound)


@pytest.mark.parametrize(
    ("field", "invalid", "message"),
    [
        ("receipt_payload_size_bytes", 0, "positive integer"),
        ("receipt_payload_size_bytes", True, "positive integer"),
        ("receipt_payload_sha256", "A" * 64, "64 lowercase hexadecimal"),
        ("receipt_payload_sha256", "0" * 63, "64 lowercase hexadecimal"),
    ],
)
def test_p132_rejects_invalid_retained_values_even_when_outer_identity_is_rebound(
    tmp_path, field, invalid, message
) -> None:
    store = _store(tmp_path)
    payload = json.loads(open(store.destination_path, encoding="utf-8").read())
    payload[field] = invalid
    rebound = _rewrite_and_rebind(store, _canonical(payload))
    with pytest.raises(ValueError, match=message):
        verify_stored_p130_receipt_identity(rebound)


@pytest.mark.parametrize(
    "flag",
    ["p130_evidence_state_verified", "p130_verification_flags_verified", "exact_readback_verified"],
)
def test_p132_rejects_each_weakened_p131_verification_flag(tmp_path, flag) -> None:
    store = _store(tmp_path)
    with pytest.raises(ValueError, match="verification flags are incomplete"):
        verify_stored_p130_receipt_identity(replace(store, **{flag: False}))


def test_p132_rejects_incompatible_p131_state_authority_type_and_outer_identity(tmp_path) -> None:
    store = _store(tmp_path)
    with pytest.raises(ValueError, match="state is incompatible"):
        verify_stored_p130_receipt_identity(replace(store, evidence_state=P131_EVIDENCE_STATE + "_DRIFT"))
    with pytest.raises(ValueError, match="must not grant automatic-control authority"):
        verify_stored_p130_receipt_identity(replace(store, automatic_control_allowed=True))
    with pytest.raises(ValueError, match="incompatible type"):
        verify_stored_p130_receipt_identity(object())
    with pytest.raises(ValueError, match="positive integer"):
        verify_stored_p130_receipt_identity(replace(store, stored_payload_size_bytes=0))
    with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
        verify_stored_p130_receipt_identity(replace(store, stored_payload_sha256="A" * 64))


def test_p132_rejects_duplicate_keys_invalid_utf8_and_non_object_json(tmp_path) -> None:
    store = _store(tmp_path)
    duplicate = (
        '{"p130_evidence_state":"%s","receipt_payload_sha256":"%s",'
        '"receipt_payload_sha256":"%s","receipt_payload_size_bytes":321}'
        % (P130_EVIDENCE_STATE, store.receipt_payload_sha256, store.receipt_payload_sha256)
    ).encode()
    rebound = _rewrite_and_rebind(store, duplicate)
    with pytest.raises(ValueError, match="duplicate key"):
        verify_stored_p130_receipt_identity(rebound)

    store = _store(tmp_path)
    rebound = _rewrite_and_rebind(store, b"\xff")
    with pytest.raises(ValueError, match="not strict UTF-8 JSON"):
        verify_stored_p130_receipt_identity(rebound)

    store = _store(tmp_path)
    rebound = _rewrite_and_rebind(store, b"[]")
    with pytest.raises(ValueError, match="must be a JSON object"):
        verify_stored_p130_receipt_identity(rebound)


def test_p132_source_override_is_explicit_and_verified(tmp_path) -> None:
    store = _store(tmp_path)
    copy = tmp_path / "copy.identity.json"
    copy.write_bytes(open(store.destination_path, "rb").read())
    verified = verify_stored_p130_receipt_identity(store, source_path=copy)
    assert verified.source_path == str(copy)


def test_p132_truth_boundary_remains_explicitly_non_authoritative(tmp_path) -> None:
    rendered = verify_stored_p130_receipt_identity(_store(tmp_path)).as_dict()
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
