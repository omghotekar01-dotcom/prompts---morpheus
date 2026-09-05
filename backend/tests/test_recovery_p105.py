import hashlib
import json
from dataclasses import replace

import pytest

from app.recovery_p100 import EVIDENCE_STATE as P100_EVIDENCE_STATE
from app.recovery_p102 import EVIDENCE_STATE as P102_EVIDENCE_STATE
from app.recovery_p103 import EVIDENCE_STATE as P103_EVIDENCE_STATE, RecoveryP100P102CompositionEvidence
from app.recovery_p104 import SCHEMA as P104_SCHEMA, canonicalize_p103_composition_receipt
from app.recovery_p105 import EVIDENCE_STATE, TRUTH_BOUNDARY, replay_p104_composition_receipt


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
}
SEMANTIC_FIELDS = (
    "sequence",
    "lineage_sha256",
    "binding_receipt_payload_sha256",
    "binding_receipt_payload_size_bytes",
    "receipt_identity_binding_sha256",
    "retained_identity_payload_sha256",
    "retained_identity_payload_size_bytes",
    "replay_stored_identity_binding_sha256",
    "replay_binding_receipt_payload_sha256",
    "replay_binding_receipt_payload_size_bytes",
    "retained_replay_identity_payload_sha256",
    "retained_replay_identity_payload_size_bytes",
    "replay_retained_identity_binding_sha256",
    "replay_retained_identity_binding_receipt_payload_sha256",
    "replay_retained_identity_binding_receipt_payload_size_bytes",
    "retained_replay_receipt_identity_payload_sha256",
    "retained_replay_receipt_identity_payload_size_bytes",
    "replay_retained_receipt_identity_binding_sha256",
    "replay_retained_receipt_identity_binding_receipt_payload_sha256",
    "replay_retained_receipt_identity_binding_receipt_payload_size_bytes",
    "retained_replayed_receipt_identity_payload_sha256",
    "retained_replayed_receipt_identity_payload_size_bytes",
    "replayed_receipt_retained_identity_binding_sha256",
    "replayed_receipt_retained_identity_binding_receipt_payload_sha256",
    "replayed_receipt_retained_identity_binding_receipt_payload_size_bytes",
    "retained_p101_record_payload_sha256",
    "retained_p101_record_payload_size_bytes",
    "p100_p102_composition_binding_sha256",
)
BINDING_INPUT_FIELDS = SEMANTIC_FIELDS[:25]


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _canonical_sha(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _p103() -> RecoveryP100P102CompositionEvidence:
    values = {}
    for index, field in enumerate(SEMANTIC_FIELDS[:-1], start=1):
        values[field] = index if field in INT_FIELDS else _sha(field)
    binding_inputs = {field: values[field] for field in BINDING_INPUT_FIELDS}
    values["p100_p102_composition_binding_sha256"] = _canonical_sha(
        {
            **binding_inputs,
            "retained_p101_record_payload_sha256": values["retained_p101_record_payload_sha256"],
            "retained_p101_record_payload_size_bytes": values["retained_p101_record_payload_size_bytes"],
            "p100_evidence_state": P100_EVIDENCE_STATE,
            "p102_evidence_state": P102_EVIDENCE_STATE,
        }
    )
    return RecoveryP100P102CompositionEvidence(
        **values,
        p100_contract_verified=True,
        p102_contract_verified=True,
        cross_evidence_identity_verified=True,
    )


def _receipt():
    return canonicalize_p103_composition_receipt(_p103())


def _repack(document: dict[str, object]) -> tuple[bytes, str, int]:
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return payload, hashlib.sha256(payload).hexdigest(), len(payload)


def test_replays_real_p103_to_p104_receipt_deterministically():
    receipt = _receipt()
    evidence = replay_p104_composition_receipt(
        receipt.payload,
        expected_payload_sha256=receipt.payload_sha256,
        expected_payload_size_bytes=receipt.payload_size_bytes,
    )
    assert evidence.sequence == receipt.sequence
    assert evidence.p100_p102_composition_binding_sha256 == receipt.p100_p102_composition_binding_sha256
    assert evidence.p104_receipt_payload_sha256 == receipt.payload_sha256
    assert evidence.p104_receipt_payload_size_bytes == receipt.payload_size_bytes
    assert evidence.expected_payload_identity_verified is True
    assert evidence.canonical_receipt_verified is True
    assert evidence.dependency_state_verified is True
    assert evidence.p100_p102_composition_binding_recomputed_verified is True
    assert evidence.p103_evidence_state == P103_EVIDENCE_STATE
    assert evidence.evidence_state == EVIDENCE_STATE
    assert evidence.automatic_control_allowed is False


def test_rejects_wrong_expected_outer_identity():
    receipt = _receipt()
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        replay_p104_composition_receipt(
            receipt.payload,
            expected_payload_sha256="0" * 64,
            expected_payload_size_bytes=receipt.payload_size_bytes,
        )
    with pytest.raises(ValueError, match="byte length mismatch"):
        replay_p104_composition_receipt(
            receipt.payload,
            expected_payload_sha256=receipt.payload_sha256,
            expected_payload_size_bytes=receipt.payload_size_bytes + 1,
        )


def test_rejects_noncanonical_json_even_with_matching_outer_identity():
    receipt = _receipt()
    document = json.loads(receipt.payload)
    payload = json.dumps(document, indent=2, sort_keys=True).encode()
    with pytest.raises(ValueError, match="strict canonical JSON"):
        replay_p104_composition_receipt(
            payload,
            expected_payload_sha256=hashlib.sha256(payload).hexdigest(),
            expected_payload_size_bytes=len(payload),
        )


@pytest.mark.parametrize("field", SEMANTIC_FIELDS)
def test_rejects_semantic_forgery_even_when_outer_identity_is_recomputed(field):
    receipt = _receipt()
    document = json.loads(receipt.payload)
    document[field] = document[field] + 1 if field in INT_FIELDS else _sha("forged-" + field)
    payload, digest, size = _repack(document)
    with pytest.raises(ValueError, match="composition binding recomputation mismatch"):
        replay_p104_composition_receipt(
            payload,
            expected_payload_sha256=digest,
            expected_payload_size_bytes=size,
        )


def test_rejects_schema_and_dependency_state_drift():
    receipt = _receipt()
    for key, value in (("schema", P104_SCHEMA + ".drift"), ("p103_evidence_state", P103_EVIDENCE_STATE + "_DRIFT")):
        document = json.loads(receipt.payload)
        document[key] = value
        payload, digest, size = _repack(document)
        with pytest.raises(ValueError, match="schema is incompatible|evidence state is incompatible"):
            replay_p104_composition_receipt(payload, expected_payload_sha256=digest, expected_payload_size_bytes=size)


def test_rejects_extra_schema_field():
    receipt = _receipt()
    document = json.loads(receipt.payload)
    document["extra"] = "not-permitted"
    payload, digest, size = _repack(document)
    with pytest.raises(ValueError, match="schema is incompatible"):
        replay_p104_composition_receipt(payload, expected_payload_sha256=digest, expected_payload_size_bytes=size)


@pytest.mark.parametrize("invalid", [True, 0, -1])
def test_rejects_invalid_positive_integer_identities(invalid):
    receipt = _receipt()
    document = json.loads(receipt.payload)
    document["sequence"] = invalid
    payload, digest, size = _repack(document)
    with pytest.raises(ValueError, match="positive integer"):
        replay_p104_composition_receipt(payload, expected_payload_sha256=digest, expected_payload_size_bytes=size)


def test_rejects_malformed_sha_identity():
    receipt = _receipt()
    document = json.loads(receipt.payload)
    document["lineage_sha256"] = "A" * 64
    payload, digest, size = _repack(document)
    with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
        replay_p104_composition_receipt(payload, expected_payload_sha256=digest, expected_payload_size_bytes=size)


@pytest.mark.parametrize("payload", [b"not-json", b"\xff", b"[]"])
def test_rejects_invalid_payload_shapes(payload):
    digest = hashlib.sha256(payload).hexdigest()
    with pytest.raises(ValueError):
        replay_p104_composition_receipt(payload, expected_payload_sha256=digest, expected_payload_size_bytes=len(payload))


def test_rejects_incompatible_payload_type():
    receipt = _receipt()
    with pytest.raises(ValueError, match="must be bytes"):
        replay_p104_composition_receipt(
            receipt.payload.decode(),
            expected_payload_sha256=receipt.payload_sha256,
            expected_payload_size_bytes=receipt.payload_size_bytes,
        )


def test_truth_boundary_remains_explicitly_non_authoritative():
    receipt = _receipt()
    evidence = replay_p104_composition_receipt(
        receipt.payload,
        expected_payload_sha256=receipt.payload_sha256,
        expected_payload_size_bytes=receipt.payload_size_bytes,
    )
    rendered = evidence.as_dict()
    assert rendered["automatic_control_allowed"] is False
    assert rendered["truth_boundary"] == TRUTH_BOUNDARY
    for phrase in (
        "does not authenticate",
        "freshness/latest/global/monotonic",
        "prevent replay or coordinated rollback",
        "authorize startup or mutation",
        "production readiness",
        "benchmark evidence",
        "novelty evidence",
    ):
        assert phrase in TRUTH_BOUNDARY
