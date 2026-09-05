import hashlib, json
import pytest
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay import EVIDENCE_STATE as P95_STATE
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay import EVIDENCE_STATE as P97_STATE
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding import EVIDENCE_STATE as P98_STATE
from app.recovery_p99 import SCHEMA
from app.recovery_p100 import EVIDENCE_STATE, TRUTH_BOUNDARY, _FIELDS, replay_recovery_startup_replayed_receipt_retained_identity_binding_receipt

def _payload():
    values={}
    n=101
    for field,kind in _FIELDS:
        if field=="replayed_receipt_retained_identity_binding_sha256":
            continue
        values[field] = hashlib.sha256(field.encode()).hexdigest() if kind=="sha" else (9 if field=="sequence" else n)
        if kind=="int" and field!="sequence": n += 1
    binding=hashlib.sha256(json.dumps({**values,"p95_evidence_state":P95_STATE,"p97_evidence_state":P97_STATE},sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    doc={"schema":SCHEMA, **values, "replayed_receipt_retained_identity_binding_sha256":binding, "p98_evidence_state":P98_STATE}
    return json.dumps(doc,sort_keys=True,separators=(",",":"),allow_nan=False).encode()

def _replay(raw):
    return replay_recovery_startup_replayed_receipt_retained_identity_binding_receipt(raw, expected_payload_sha256=hashlib.sha256(raw).hexdigest(), expected_payload_size_bytes=len(raw))

def test_p100_replays_canonical_receipt_and_recomputes_binding():
    result=_replay(_payload())
    assert result.expected_payload_identity_verified and result.canonical_receipt_verified
    assert result.dependency_state_verified and result.replayed_receipt_retained_identity_binding_recomputed_verified
    assert result.evidence_state == EVIDENCE_STATE and result.automatic_control_allowed is False

def test_p100_rejects_outer_identity_and_noncanonical_bytes():
    raw=_payload()
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        replay_recovery_startup_replayed_receipt_retained_identity_binding_receipt(raw, expected_payload_sha256="0"*64, expected_payload_size_bytes=len(raw))
    pretty=json.dumps(json.loads(raw), indent=2).encode()
    with pytest.raises(ValueError, match="canonical JSON"):
        replay_recovery_startup_replayed_receipt_retained_identity_binding_receipt(pretty, expected_payload_sha256=hashlib.sha256(pretty).hexdigest(), expected_payload_size_bytes=len(pretty))

def test_p100_rejects_recomputed_binding_forgery():
    doc=json.loads(_payload()); doc["lineage_sha256"]="a"*64
    forged=json.dumps(doc,sort_keys=True,separators=(",",":")).encode()
    with pytest.raises(ValueError, match="recomputation mismatch"):
        _replay(forged)

@pytest.mark.parametrize("field,kind", _FIELDS)
def test_p100_validates_every_serialized_identity(field, kind):
    doc=json.loads(_payload()); doc[field] = True if kind=="int" else "Z"*64
    raw=json.dumps(doc,sort_keys=True,separators=(",",":")).encode()
    with pytest.raises(ValueError):
        _replay(raw)

def test_p100_rejects_schema_state_and_extra_fields():
    for mutation in ("schema","state","extra"):
        doc=json.loads(_payload())
        if mutation=="schema": doc["schema"]="wrong"
        elif mutation=="state": doc["p98_evidence_state"]="wrong"
        else: doc["extra"]=1
        raw=json.dumps(doc,sort_keys=True,separators=(",",":")).encode()
        with pytest.raises(ValueError): _replay(raw)

def test_p100_truth_boundary_remains_non_authoritative():
    for phrase in ("read-only","freshness","startup","benchmark evidence","novelty evidence"):
        assert phrase in TRUTH_BOUNDARY.lower()
