from __future__ import annotations

import hashlib
import json

from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay import (
    EVIDENCE_STATE as P80_EVIDENCE_STATE,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay import (
    EVIDENCE_STATE as P82_EVIDENCE_STATE,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding import (
    EVIDENCE_STATE as P83_EVIDENCE_STATE,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt import (
    SCHEMA as P84_SCHEMA,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay import (
    EVIDENCE_STATE as P85_EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    replay_recovery_startup_replay_stored_identity_binding_receipt,
)


def _canonical(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def test_p85_exported_evidence_preserves_verified_non_authority_contract() -> None:
    payload: dict[str, object] = {
        "schema": P84_SCHEMA,
        "sequence": 17,
        "lineage_sha256": "a" * 64,
        "binding_receipt_payload_sha256": "b" * 64,
        "binding_receipt_payload_size_bytes": 512,
        "receipt_identity_binding_sha256": "c" * 64,
        "retained_identity_payload_sha256": "d" * 64,
        "retained_identity_payload_size_bytes": 256,
        "p83_evidence_state": P83_EVIDENCE_STATE,
    }
    binding_payload = {
        "sequence": payload["sequence"],
        "lineage_sha256": payload["lineage_sha256"],
        "binding_receipt_payload_sha256": payload["binding_receipt_payload_sha256"],
        "binding_receipt_payload_size_bytes": payload["binding_receipt_payload_size_bytes"],
        "receipt_identity_binding_sha256": payload["receipt_identity_binding_sha256"],
        "retained_identity_payload_sha256": payload["retained_identity_payload_sha256"],
        "retained_identity_payload_size_bytes": payload["retained_identity_payload_size_bytes"],
        "p80_evidence_state": P80_EVIDENCE_STATE,
        "p82_evidence_state": P82_EVIDENCE_STATE,
    }
    payload["replay_stored_identity_binding_sha256"] = hashlib.sha256(_canonical(binding_payload)).hexdigest()
    raw = _canonical(payload)

    evidence = replay_recovery_startup_replay_stored_identity_binding_receipt(
        raw,
        expected_payload_sha256=hashlib.sha256(raw).hexdigest(),
        expected_payload_size_bytes=len(raw),
    )
    exported = evidence.as_dict()

    assert exported["evidence_state"] == P85_EVIDENCE_STATE
    assert exported["expected_payload_identity_verified"] is True
    assert exported["canonical_receipt_verified"] is True
    assert exported["dependency_state_verified"] is True
    assert exported["replay_stored_identity_binding_recomputed_verified"] is True
    assert exported["automatic_control_allowed"] is False
    assert exported["truth_boundary"] == TRUTH_BOUNDARY
    assert "read-only" in exported["truth_boundary"]
    assert "authorize startup" in exported["truth_boundary"]
