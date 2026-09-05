from dataclasses import replace
import hashlib, json
import pytest
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding import (
    RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence,
)
from app.recovery_p99 import EVIDENCE_STATE, SCHEMA, TRUTH_BOUNDARY, _FIELDS, canonicalize_recovery_startup_p95_p97_replay_composition_binding_receipt

def _evidence():
    values = {}
    s = 101
    for field,kind in _FIELDS:
        values[field] = hashlib.sha256(f"p99-{field}".encode()).hexdigest() if kind=="sha" else (7 if field=="sequence" else s)
        if kind=="int" and field!="sequence": s += 1
    return RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoredReplayBindingEvidence(
        **values, p95_contract_verified=True, p97_contract_verified=True, cross_evidence_identity_verified=True
    )

def test_p99_canonicalizes_deterministically_and_identifies_exact_bytes():
    result = canonicalize_recovery_startup_p95_p97_replay_composition_binding_receipt(_evidence())
    decoded = json.loads(result.payload)
    assert result.payload == json.dumps(decoded, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    assert result.payload_sha256 == hashlib.sha256(result.payload).hexdigest()
    assert result.payload_size_bytes == len(result.payload)
    assert decoded["schema"] == SCHEMA
    assert result.evidence_state == EVIDENCE_STATE
    assert result.automatic_control_allowed is False

@pytest.mark.parametrize("flag", ["p95_contract_verified","p97_contract_verified","cross_evidence_identity_verified"])
def test_p99_rejects_weakened_contract(flag):
    with pytest.raises(ValueError, match="verification flags"):
        canonicalize_recovery_startup_p95_p97_replay_composition_binding_receipt(replace(_evidence(), **{flag:False}))

@pytest.mark.parametrize("field,kind", _FIELDS)
def test_p99_payload_identity_changes_for_every_semantic_field(field, kind):
    base = _evidence()
    first = canonicalize_recovery_startup_p95_p97_replay_composition_binding_receipt(base)
    value = 9999 if kind=="int" else hashlib.sha256(f"changed-{field}".encode()).hexdigest()
    second = canonicalize_recovery_startup_p95_p97_replay_composition_binding_receipt(replace(base, **{field:value}))
    assert second.payload_sha256 != first.payload_sha256

def test_p99_rejects_state_control_and_bad_identity():
    with pytest.raises(ValueError, match="state"):
        canonicalize_recovery_startup_p95_p97_replay_composition_binding_receipt(replace(_evidence(), evidence_state="DRIFT"))
    with pytest.raises(ValueError, match="must not grant"):
        canonicalize_recovery_startup_p95_p97_replay_composition_binding_receipt(replace(_evidence(), automatic_control_allowed=True))
    with pytest.raises(ValueError, match="positive integer"):
        canonicalize_recovery_startup_p95_p97_replay_composition_binding_receipt(replace(_evidence(), sequence=True))
    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        canonicalize_recovery_startup_p95_p97_replay_composition_binding_receipt(replace(_evidence(), lineage_sha256="Z"*64))

def test_p99_truth_boundary_remains_non_authoritative():
    for phrase in ("read-only","freshness","startup","benchmark evidence","novelty evidence"):
        assert phrase in TRUTH_BOUNDARY.lower()
