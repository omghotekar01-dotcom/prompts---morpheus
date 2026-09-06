import hashlib
import json
from dataclasses import replace

import pytest

from app.recovery_p123 import EVIDENCE_STATE as P123_EVIDENCE_STATE
from app.recovery_p125 import RecoveryP124ReplayEvidence
from app.recovery_p126 import EVIDENCE_STATE as P126_EVIDENCE_STATE, _FIELDS, store_p125_replay_identity
from app.recovery_p127 import EVIDENCE_STATE, TRUTH_BOUNDARY, verify_stored_p125_replay_identity


INT_FIELDS = {field for field, kind in _FIELDS if kind == "int"}
FIELDS = tuple(field for field, _ in _FIELDS)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _p125_evidence() -> RecoveryP124ReplayEvidence:
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


def _store(tmp_path):
    return store_p125_replay_identity(
        _p125_evidence(), destination_path=tmp_path / "p125.identity.json"
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


def test_independently_verifies_exact_stored_p126_identity(tmp_path):
    store = _store(tmp_path)
    verified = verify_stored_p125_replay_identity(store)
    assert verified.stored_payload_sha256 == store.stored_payload_sha256
    assert verified.stored_payload_size_bytes == store.stored_payload_size_bytes
    assert verified.source_path == store.destination_path
    assert verified.exact_size_verified is True
    assert verified.exact_sha256_verified is True
    assert verified.strict_schema_verified is True
    assert verified.canonical_encoding_verified is True
    assert verified.retained_identity_verified is True
    assert verified.p125_evidence_state_verified is True
    assert verified.evidence_state == EVIDENCE_STATE
    assert verified.automatic_control_allowed is False


def test_rejects_missing_or_tampered_stored_bytes(tmp_path):
    store = _store(tmp_path)
    with open(store.destination_path, "ab") as handle:
        handle.write(b"x")
    with pytest.raises(ValueError, match="size mismatch"):
        verify_stored_p125_replay_identity(store)

    store = _store(tmp_path)
    payload = bytearray(open(store.destination_path, "rb").read())
    payload[-2] = ord("0") if payload[-2] != ord("0") else ord("1")
    with open(store.destination_path, "wb") as handle:
        handle.write(payload)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_stored_p125_replay_identity(store)


def test_rejects_noncanonical_json_even_when_digest_and_size_are_rebound(tmp_path):
    store = _store(tmp_path)
    payload = json.loads(open(store.destination_path, encoding="utf-8").read())
    pretty = json.dumps(payload, sort_keys=True, indent=2).encode()
    rebound = _rewrite_and_rebind(store, pretty)
    with pytest.raises(ValueError, match="not canonically encoded"):
        verify_stored_p125_replay_identity(rebound)


def test_rejects_unknown_schema_even_when_digest_is_rebound(tmp_path):
    store = _store(tmp_path)
    payload = json.loads(open(store.destination_path, encoding="utf-8").read())
    payload["unexpected"] = "field"
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    rebound = _rewrite_and_rebind(store, encoded)
    with pytest.raises(ValueError, match="schema mismatch"):
        verify_stored_p125_replay_identity(rebound)


def test_rejects_retained_field_drift_even_when_file_identity_is_rebound(tmp_path):
    store = _store(tmp_path)
    field = FIELDS[0]
    payload = json.loads(open(store.destination_path, encoding="utf-8").read())
    payload[field] = payload[field] + 1 if field in INT_FIELDS else _sha("drift")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    rebound = _rewrite_and_rebind(store, encoded)
    with pytest.raises(ValueError, match=f"field mismatch: {field}"):
        verify_stored_p125_replay_identity(rebound)


def test_rejects_weakened_or_incompatible_p126_evidence(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(ValueError, match="state is incompatible"):
        verify_stored_p125_replay_identity(
            replace(store, evidence_state=P126_EVIDENCE_STATE + "_DRIFT")
        )
    with pytest.raises(ValueError, match="must not grant automatic-control authority"):
        verify_stored_p125_replay_identity(replace(store, automatic_control_allowed=True))
    with pytest.raises(ValueError, match="verification flags are incomplete"):
        verify_stored_p125_replay_identity(replace(store, exact_readback_verified=False))


def test_source_override_is_explicit_and_verified(tmp_path):
    store = _store(tmp_path)
    copy = tmp_path / "copy.identity.json"
    copy.write_bytes(open(store.destination_path, "rb").read())
    verified = verify_stored_p125_replay_identity(store, source_path=copy)
    assert verified.source_path == str(copy)


def test_truth_boundary_remains_explicitly_non_authoritative(tmp_path):
    rendered = verify_stored_p125_replay_identity(_store(tmp_path)).as_dict()
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
