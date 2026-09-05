from __future__ import annotations

import hashlib
import json

import pytest

from app.recovery_p103 import EVIDENCE_STATE as P103_EVIDENCE_STATE
from app.recovery_p105 import EVIDENCE_STATE as P105_EVIDENCE_STATE
from app.recovery_p107 import EVIDENCE_STATE as P107_EVIDENCE_STATE
from app.recovery_p108 import EVIDENCE_STATE as P108_EVIDENCE_STATE, _FIELDS as P108_SHARED_FIELDS, RecoveryP105P107CompositionEvidence
from app.recovery_p109 import SCHEMA as P109_SCHEMA, _FIELDS as P109_FIELDS, canonicalize_p108_composition_receipt
from app.recovery_p110 import EVIDENCE_STATE, TRUTH_BOUNDARY, replay_p109_composition_receipt


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _canonical(document: object) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _binding(values: dict[str, object]) -> str:
    payload = {
        **{field: values[field] for field, _ in P108_SHARED_FIELDS},
        "retained_p106_record_payload_sha256": values["retained_p106_record_payload_sha256"],
        "retained_p106_record_payload_size_bytes": values["retained_p106_record_payload_size_bytes"],
        "p103_evidence_state": P103_EVIDENCE_STATE,
        "p105_evidence_state": P105_EVIDENCE_STATE,
        "p107_evidence_state": P107_EVIDENCE_STATE,
    }
    return hashlib.sha256(_canonical(payload)).hexdigest()


def _p108() -> RecoveryP105P107CompositionEvidence:
    values: dict[str, object] = {}
    n = 17
    for field, kind in P109_FIELDS:
        if field == "p105_p107_composition_binding_sha256":
            continue
        if kind == "int":
            values[field] = n
            n += 11
        else:
            values[field] = _sha(field)
    values["p105_p107_composition_binding_sha256"] = _binding(values)
    return RecoveryP105P107CompositionEvidence(
        **values,
        p105_contract_verified=True,
        p107_contract_verified=True,
        cross_evidence_identity_verified=True,
    )


def _receipt() -> tuple[bytes, str, int]:
    receipt = canonicalize_p108_composition_receipt(_p108())
    return receipt.payload, receipt.payload_sha256, receipt.payload_size_bytes


def _reidentity(document: object) -> tuple[bytes, str, int]:
    payload = _canonical(document)
    return payload, hashlib.sha256(payload).hexdigest(), len(payload)


def test_p110_replays_real_p108_p109_path_and_is_non_authoritative() -> None:
    payload, sha, size = _receipt()
    evidence = replay_p109_composition_receipt(
        payload, expected_payload_sha256=sha, expected_payload_size_bytes=size
    )
    assert evidence.evidence_state == EVIDENCE_STATE
    assert evidence.automatic_control_allowed is False
    assert evidence.expected_payload_identity_verified
    assert evidence.canonical_receipt_verified
    assert evidence.dependency_state_verified
    assert evidence.p105_p107_composition_binding_recomputed_verified
    assert evidence.p108_evidence_state == P108_EVIDENCE_STATE
    assert evidence.p109_receipt_payload_sha256 == sha
    assert evidence.p109_receipt_payload_size_bytes == size


def test_p110_rejects_wrong_outer_identity() -> None:
    payload, sha, size = _receipt()
    with pytest.raises(ValueError, match="byte length mismatch"):
        replay_p109_composition_receipt(
            payload, expected_payload_sha256=sha, expected_payload_size_bytes=size + 1
        )
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        replay_p109_composition_receipt(
            payload, expected_payload_sha256=_sha("wrong"), expected_payload_size_bytes=size
        )


@pytest.mark.parametrize("bad_size", [False, 0, -1])
def test_p110_rejects_invalid_expected_size(bad_size: object) -> None:
    payload, sha, _ = _receipt()
    with pytest.raises(ValueError, match="positive integer"):
        replay_p109_composition_receipt(
            payload, expected_payload_sha256=sha, expected_payload_size_bytes=bad_size  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("bad_sha", ["A" * 64, "0" * 63, "g" * 64])
def test_p110_rejects_invalid_expected_sha(bad_sha: str) -> None:
    payload, _, size = _receipt()
    with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
        replay_p109_composition_receipt(
            payload, expected_payload_sha256=bad_sha, expected_payload_size_bytes=size
        )


def test_p110_rejects_noncanonical_json_even_with_recomputed_outer_identity() -> None:
    payload, _, _ = _receipt()
    document = json.loads(payload)
    noncanonical = json.dumps(document, sort_keys=False, indent=2).encode()
    with pytest.raises(ValueError, match="strict canonical JSON"):
        replay_p109_composition_receipt(
            noncanonical,
            expected_payload_sha256=hashlib.sha256(noncanonical).hexdigest(),
            expected_payload_size_bytes=len(noncanonical),
        )


@pytest.mark.parametrize("mutation", ["schema", "state", "extra", "missing"])
def test_p110_rejects_schema_or_dependency_state_drift_with_recomputed_outer_identity(mutation: str) -> None:
    payload, _, _ = _receipt()
    document = json.loads(payload)
    if mutation == "schema":
        document["schema"] = "forged"
    elif mutation == "state":
        document["p108_evidence_state"] = "forged"
    elif mutation == "extra":
        document["unexpected"] = 1
    else:
        document.pop("lineage_sha256")
    forged, forged_sha, forged_size = _reidentity(document)
    expected = "evidence state" if mutation == "state" else "schema"
    with pytest.raises(ValueError, match=expected):
        replay_p109_composition_receipt(
            forged, expected_payload_sha256=forged_sha, expected_payload_size_bytes=forged_size
        )


@pytest.mark.parametrize("field,kind", P109_FIELDS)
def test_p110_rejects_every_semantic_tamper_even_when_outer_identity_is_recomputed(field: str, kind: str) -> None:
    payload, _, _ = _receipt()
    document = json.loads(payload)
    document[field] = document[field] + 1 if kind == "int" else _sha("forged-" + field)
    forged, forged_sha, forged_size = _reidentity(document)
    with pytest.raises(ValueError):
        replay_p109_composition_receipt(
            forged, expected_payload_sha256=forged_sha, expected_payload_size_bytes=forged_size
        )


@pytest.mark.parametrize("field,kind", P109_FIELDS)
def test_p110_rejects_invalid_serialized_identity_types(field: str, kind: str) -> None:
    payload, _, _ = _receipt()
    document = json.loads(payload)
    document[field] = False if kind == "int" else "A" * 64
    forged, forged_sha, forged_size = _reidentity(document)
    with pytest.raises(ValueError):
        replay_p109_composition_receipt(
            forged, expected_payload_sha256=forged_sha, expected_payload_size_bytes=forged_size
        )


@pytest.mark.parametrize(
    "payload",
    [
        b"\xff",
        b"{",
        b"[]",
    ],
)
def test_p110_rejects_invalid_utf8_json_or_non_object(payload: bytes) -> None:
    with pytest.raises(ValueError):
        replay_p109_composition_receipt(
            payload,
            expected_payload_sha256=hashlib.sha256(payload).hexdigest(),
            expected_payload_size_bytes=len(payload),
        )


def test_p110_rejects_non_bytes_payload() -> None:
    with pytest.raises(ValueError, match="must be bytes"):
        replay_p109_composition_receipt(  # type: ignore[arg-type]
            "{}", expected_payload_sha256=_sha("x"), expected_payload_size_bytes=2
        )


def test_p110_truth_boundary_is_explicit() -> None:
    assert "does not authenticate" in TRUTH_BOUNDARY
    assert "freshness/latest/global/monotonic" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark evidence" in TRUTH_BOUNDARY
    assert "novelty evidence" in TRUTH_BOUNDARY
    assert "automatic-control authority" in TRUTH_BOUNDARY
