from dataclasses import replace
import hashlib
import json

import pytest

from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay import EVIDENCE_STATE as P90_EVIDENCE_STATE
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay import EVIDENCE_STATE as P92_EVIDENCE_STATE
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding import (
    EVIDENCE_STATE as P93_EVIDENCE_STATE,
    RecoveryStartupReplayRetainedIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt import (
    SCHEMA as P94_SCHEMA,
    canonicalize_recovery_startup_replay_retained_receipt_identity_binding_receipt,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    replay_recovery_startup_replay_retained_receipt_identity_binding_receipt,
)

H = {str(i): f"{i:x}" * 64 for i in range(1, 10)}
H.update({"a": "a" * 64, "b": "b" * 64, "c": "c" * 64, "d": "d" * 64, "e": "e" * 64})


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def semantic_values():
    return {
        "sequence": 17,
        "lineage_sha256": H["1"],
        "binding_receipt_payload_sha256": H["2"],
        "binding_receipt_payload_size_bytes": 101,
        "receipt_identity_binding_sha256": H["3"],
        "retained_identity_payload_sha256": H["4"],
        "retained_identity_payload_size_bytes": 202,
        "replay_stored_identity_binding_sha256": H["5"],
        "replay_binding_receipt_payload_sha256": H["6"],
        "replay_binding_receipt_payload_size_bytes": 303,
        "retained_replay_identity_payload_sha256": H["7"],
        "retained_replay_identity_payload_size_bytes": 404,
        "replay_retained_identity_binding_sha256": H["8"],
        "replay_retained_identity_binding_receipt_payload_sha256": H["9"],
        "replay_retained_identity_binding_receipt_payload_size_bytes": 505,
        "retained_replay_receipt_identity_payload_sha256": H["a"],
        "retained_replay_receipt_identity_payload_size_bytes": 606,
    }


def p93():
    values = semantic_values()
    binding = canonical_sha({**values, "p90_evidence_state": P90_EVIDENCE_STATE, "p92_evidence_state": P92_EVIDENCE_STATE})
    return RecoveryStartupReplayRetainedIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence(
        **values,
        replay_retained_receipt_identity_binding_sha256=binding,
        p90_contract_verified=True,
        p92_contract_verified=True,
        cross_evidence_identity_verified=True,
    )


def receipt():
    return canonicalize_recovery_startup_replay_retained_receipt_identity_binding_receipt(p93())


def replay(payload=None, sha=None, size=None):
    encoded = receipt() if payload is None else None
    raw = encoded.payload if payload is None else payload
    return replay_recovery_startup_replay_retained_receipt_identity_binding_receipt(
        raw,
        expected_payload_sha256=(encoded.payload_sha256 if sha is None and encoded else hashlib.sha256(raw).hexdigest() if sha is None else sha),
        expected_payload_size_bytes=(encoded.payload_size_bytes if size is None and encoded else len(raw) if size is None else size),
    )


def test_p95_replays_real_p93_to_p94_receipt_deterministically():
    first = replay()
    second = replay()
    assert first == second
    assert first.evidence_state == EVIDENCE_STATE
    assert first.p93_evidence_state == P93_EVIDENCE_STATE
    assert first.expected_payload_identity_verified is True
    assert first.canonical_receipt_verified is True
    assert first.dependency_state_verified is True
    assert first.replay_retained_receipt_identity_binding_recomputed_verified is True
    assert first.automatic_control_allowed is False


@pytest.mark.parametrize("bad_sha,bad_size", [(H["b"], None), (None, 1)])
def test_p95_rejects_wrong_expected_outer_identity(bad_sha, bad_size):
    encoded = receipt()
    with pytest.raises(ValueError, match="mismatch"):
        replay(encoded.payload, sha=bad_sha or encoded.payload_sha256, size=bad_size or encoded.payload_size_bytes)


def test_p95_rejects_noncanonical_json_even_when_outer_identity_matches():
    doc = json.loads(receipt().payload)
    raw = json.dumps(doc, indent=2, sort_keys=True).encode()
    with pytest.raises(ValueError, match="strict canonical JSON"):
        replay(raw)


@pytest.mark.parametrize("field,value,match", [
    ("schema", "wrong", "schema identifier"),
    ("p93_evidence_state", "wrong", "P93 evidence state"),
    ("sequence", True, "positive integer"),
    ("lineage_sha256", "A" * 64, "lowercase hexadecimal"),
])
def test_p95_rejects_schema_state_and_semantic_shape_drift(field, value, match):
    doc = json.loads(receipt().payload)
    doc[field] = value
    raw = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match=match):
        replay(raw)


def test_p95_rejects_extra_schema_field():
    doc = json.loads(receipt().payload)
    doc["unexpected"] = 1
    raw = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="schema is incompatible"):
        replay(raw)


def test_p95_rejects_forged_serialized_p93_binding_even_with_recomputed_outer_identity():
    doc = json.loads(receipt().payload)
    doc["replay_retained_receipt_identity_binding_sha256"] = H["d"]
    raw = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="binding recomputation mismatch"):
        replay(raw)


def test_p95_rejects_semantic_tamper_without_recomputed_p93_binding():
    doc = json.loads(receipt().payload)
    doc["retained_replay_receipt_identity_payload_size_bytes"] += 1
    raw = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError, match="binding recomputation mismatch"):
        replay(raw)


def test_p95_rejects_non_bytes_input():
    with pytest.raises(ValueError, match="must be bytes"):
        replay_recovery_startup_replay_retained_receipt_identity_binding_receipt(
            "not-bytes", expected_payload_sha256=H["1"], expected_payload_size_bytes=1
        )


def test_p95_truth_boundary_stays_read_only_and_non_claiming():
    evidence = replay()
    exported = evidence.as_dict()
    assert exported["automatic_control_allowed"] is False
    assert exported["truth_boundary"] == TRUTH_BOUNDARY
    lower = TRUTH_BOUNDARY.lower()
    for phrase in ("does not authenticate", "freshness", "authorize startup or mutation", "production readiness", "benchmark evidence", "novelty evidence"):
        assert phrase in lower
