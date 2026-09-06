from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.recovery_p128 import RecoveryP125P127CompositionEvidence
from app.recovery_p129 import _FIELDS, canonicalize_p128_composition_receipt
from app.recovery_p130 import EVIDENCE_STATE, TRUTH_BOUNDARY, verify_p129_composition_receipt


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _p128() -> RecoveryP125P127CompositionEvidence:
    values: dict[str, object] = {}
    n = 31
    for field, kind in _FIELDS:
        values[field] = n if kind == "int" else _sha(field)
        if kind == "int":
            n += 17
    values.update(
        {
            "p125_contract_verified": True,
            "p127_contract_verified": True,
            "cross_evidence_identity_verified": True,
        }
    )
    return RecoveryP125P127CompositionEvidence(**values)


def _receipt():
    return canonicalize_p128_composition_receipt(_p128())


def _forged_receipt(payload: bytes):
    receipt = _receipt()
    return replace(
        receipt,
        payload=payload,
        payload_sha256=hashlib.sha256(payload).hexdigest(),
        payload_size_bytes=len(payload),
    )


def test_p130_verifies_exact_canonical_receipt_without_authority() -> None:
    receipt = _receipt()
    verified = verify_p129_composition_receipt(receipt, receipt.payload)
    assert verified.evidence_state == EVIDENCE_STATE
    assert verified.automatic_control_allowed is False
    assert verified.receipt_payload_sha256 == receipt.payload_sha256
    assert verified.receipt_payload_size_bytes == receipt.payload_size_bytes
    assert verified.exact_size_verified
    assert verified.exact_sha256_verified
    assert verified.strict_schema_verified
    assert verified.canonical_encoding_verified
    assert verified.retained_identity_verified
    assert verified.p128_evidence_state_verified
    assert verified.p129_contract_verified
    assert verified.as_dict()["truth_boundary"] == TRUTH_BOUNDARY


def test_p130_rejects_incompatible_evidence_and_authority_drift() -> None:
    receipt = _receipt()
    with pytest.raises(ValueError, match="incompatible type"):
        verify_p129_composition_receipt(object(), receipt.payload)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="state"):
        verify_p129_composition_receipt(replace(receipt, evidence_state="forged"), receipt.payload)
    with pytest.raises(ValueError, match="automatic-control"):
        verify_p129_composition_receipt(replace(receipt, automatic_control_allowed=True), receipt.payload)
    with pytest.raises(ValueError, match="verification flags"):
        verify_p129_composition_receipt(replace(receipt, canonical_receipt_verified=False), receipt.payload)


def test_p130_rejects_payload_identity_mismatch() -> None:
    receipt = _receipt()
    with pytest.raises(ValueError, match="size mismatch"):
        verify_p129_composition_receipt(receipt, receipt.payload + b" ")
    tampered = bytearray(receipt.payload)
    tampered[-2] = ord("0") if tampered[-2] != ord("0") else ord("1")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_p129_composition_receipt(receipt, bytes(tampered))


def test_p130_rejects_non_bytes_payload() -> None:
    receipt = _receipt()
    with pytest.raises(ValueError, match="must be bytes"):
        verify_p129_composition_receipt(receipt, receipt.payload.decode())  # type: ignore[arg-type]


def test_p130_rejects_duplicate_keys_even_when_metadata_matches() -> None:
    receipt = _receipt()
    document = json.loads(receipt.payload)
    body = receipt.payload.decode()
    first_key = next(iter(document))
    marker = "{"
    duplicate = (marker + json.dumps(first_key) + ":" + json.dumps(document[first_key]) + "," + body[1:]).encode()
    forged = _forged_receipt(duplicate)
    with pytest.raises(ValueError, match="duplicate key"):
        verify_p129_composition_receipt(forged, duplicate)


def test_p130_rejects_schema_and_canonical_encoding_drift() -> None:
    receipt = _receipt()
    document = json.loads(receipt.payload)

    bad_schema = {**document, "schema": "morpheus.recovery.forged"}
    encoded_bad_schema = json.dumps(bad_schema, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="schema identifier"):
        verify_p129_composition_receipt(_forged_receipt(encoded_bad_schema), encoded_bad_schema)

    pretty = json.dumps(document, sort_keys=True, indent=2).encode()
    with pytest.raises(ValueError, match="canonically encoded"):
        verify_p129_composition_receipt(_forged_receipt(pretty), pretty)


def test_p130_truth_boundary_stays_explicit() -> None:
    assert "does not authenticate" in TRUTH_BOUNDARY
    assert "freshness/latest/global/monotonic" in TRUTH_BOUNDARY
    assert "authorize startup or mutation" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "automatic-control authority" in TRUTH_BOUNDARY
