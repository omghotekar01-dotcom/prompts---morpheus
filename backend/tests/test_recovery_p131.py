from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.recovery_p130 import EVIDENCE_STATE as P130_EVIDENCE_STATE
from app.recovery_p130 import RecoveryP129ReceiptVerificationEvidence
from app.recovery_p131 import EVIDENCE_STATE, TRUTH_BOUNDARY, store_p130_receipt_identity


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _verified() -> RecoveryP129ReceiptVerificationEvidence:
    return RecoveryP129ReceiptVerificationEvidence(
        receipt_payload_sha256=_sha("p129-receipt"),
        receipt_payload_size_bytes=417,
        exact_size_verified=True,
        exact_sha256_verified=True,
        strict_schema_verified=True,
        canonical_encoding_verified=True,
        retained_identity_verified=True,
        p128_evidence_state_verified=True,
        p129_contract_verified=True,
    )


def test_p131_stores_minimum_canonical_p130_identity(tmp_path) -> None:
    destination = tmp_path / "nested" / "p130-identity.json"
    evidence = _verified()
    stored = store_p130_receipt_identity(evidence, destination_path=destination)

    payload = destination.read_bytes()
    expected_document = {
        "p130_evidence_state": P130_EVIDENCE_STATE,
        "receipt_payload_sha256": evidence.receipt_payload_sha256,
        "receipt_payload_size_bytes": evidence.receipt_payload_size_bytes,
    }
    expected = json.dumps(expected_document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

    assert payload == expected
    assert stored.evidence_state == EVIDENCE_STATE
    assert stored.automatic_control_allowed is False
    assert stored.receipt_payload_sha256 == evidence.receipt_payload_sha256
    assert stored.receipt_payload_size_bytes == evidence.receipt_payload_size_bytes
    assert stored.stored_payload_sha256 == hashlib.sha256(expected).hexdigest()
    assert stored.stored_payload_size_bytes == len(expected)
    assert stored.destination_path == str(destination)
    assert stored.p130_evidence_state_verified
    assert stored.p130_verification_flags_verified
    assert stored.exact_readback_verified
    assert list(destination.parent.glob(f".{destination.name}.*.tmp")) == []


def test_p131_replacement_is_deterministic(tmp_path) -> None:
    destination = tmp_path / "p130-identity.json"
    first = store_p130_receipt_identity(_verified(), destination_path=destination)
    first_bytes = destination.read_bytes()
    second = store_p130_receipt_identity(_verified(), destination_path=destination)
    assert destination.read_bytes() == first_bytes
    assert second.stored_payload_sha256 == first.stored_payload_sha256
    assert second.stored_payload_size_bytes == first.stored_payload_size_bytes


def test_p131_atomic_publish_failure_cleans_temporary_file(tmp_path, monkeypatch) -> None:
    destination = tmp_path / "p130-identity.json"

    def _fail_replace(*_args, **_kwargs) -> None:
        raise OSError("simulated atomic publish failure")

    monkeypatch.setattr("app.recovery_p131.os.replace", _fail_replace)

    with pytest.raises(OSError, match="simulated atomic publish failure"):
        store_p130_receipt_identity(_verified(), destination_path=destination)

    assert not destination.exists()
    assert list(tmp_path.glob(f".{destination.name}.*.tmp")) == []


def test_p131_rejects_incompatible_state_authority_and_type(tmp_path) -> None:
    destination = tmp_path / "p130-identity.json"
    evidence = _verified()
    with pytest.raises(ValueError, match="incompatible type"):
        store_p130_receipt_identity(object(), destination_path=destination)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="state"):
        store_p130_receipt_identity(replace(evidence, evidence_state="forged"), destination_path=destination)
    with pytest.raises(ValueError, match="automatic-control"):
        store_p130_receipt_identity(replace(evidence, automatic_control_allowed=True), destination_path=destination)


@pytest.mark.parametrize(
    "flag",
    [
        "exact_size_verified",
        "exact_sha256_verified",
        "strict_schema_verified",
        "canonical_encoding_verified",
        "retained_identity_verified",
        "p128_evidence_state_verified",
        "p129_contract_verified",
    ],
)
def test_p131_rejects_weakened_p130_verification_flags(tmp_path, flag: str) -> None:
    evidence = replace(_verified(), **{flag: False})
    with pytest.raises(ValueError, match="flags are incomplete"):
        store_p130_receipt_identity(evidence, destination_path=tmp_path / "identity.json")


@pytest.mark.parametrize("bad_size", [0, -1, True, 1.5, "17"])
def test_p131_rejects_invalid_receipt_size(tmp_path, bad_size: object) -> None:
    evidence = replace(_verified(), receipt_payload_size_bytes=bad_size)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="positive integer"):
        store_p130_receipt_identity(evidence, destination_path=tmp_path / "identity.json")


@pytest.mark.parametrize("bad_sha", ["", "a" * 63, "A" * 64, "g" * 64, 7])
def test_p131_rejects_invalid_receipt_sha(tmp_path, bad_sha: object) -> None:
    evidence = replace(_verified(), receipt_payload_sha256=bad_sha)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
        store_p130_receipt_identity(evidence, destination_path=tmp_path / "identity.json")


def test_p131_identity_changes_with_each_retained_semantic_field(tmp_path) -> None:
    baseline = store_p130_receipt_identity(_verified(), destination_path=tmp_path / "baseline.json")
    changed_sha = store_p130_receipt_identity(
        replace(_verified(), receipt_payload_sha256=_sha("different")),
        destination_path=tmp_path / "sha.json",
    )
    changed_size = store_p130_receipt_identity(
        replace(_verified(), receipt_payload_size_bytes=418),
        destination_path=tmp_path / "size.json",
    )
    assert changed_sha.stored_payload_sha256 != baseline.stored_payload_sha256
    assert changed_size.stored_payload_sha256 != baseline.stored_payload_sha256


def test_p131_truth_boundary_stays_explicit() -> None:
    assert "local historical evidence" in TRUTH_BOUNDARY
    assert "does not authenticate" in TRUTH_BOUNDARY
    assert "freshness/latest/global/monotonic" in TRUTH_BOUNDARY
    assert "authorize startup or mutation" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark evidence" in TRUTH_BOUNDARY
    assert "novelty evidence" in TRUTH_BOUNDARY
    assert "automatic-control authority" in TRUTH_BOUNDARY
