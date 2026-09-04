from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.dataplane_recovery_startup_receipt_identity_binding import (
    EVIDENCE_STATE as P78_EVIDENCE_STATE,
    RecoveryStartupStoredReceiptBindingEvidence,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    encode_recovery_startup_stored_receipt_binding_receipt,
)


def _p78() -> RecoveryStartupStoredReceiptBindingEvidence:
    return RecoveryStartupStoredReceiptBindingEvidence(
        sequence=7,
        lineage_sha256="a" * 64,
        receipt_payload_sha256="b" * 64,
        receipt_payload_size_bytes=321,
        admission_binding_sha256="c" * 64,
        stored_identity_payload_sha256="d" * 64,
        stored_identity_payload_size_bytes=256,
        receipt_identity_binding_sha256="e" * 64,
        p75_contract_verified=True,
        p77_contract_verified=True,
        cross_evidence_identity_verified=True,
    )


def test_p79_emits_deterministic_canonical_binding_receipt() -> None:
    first = encode_recovery_startup_stored_receipt_binding_receipt(_p78())
    second = encode_recovery_startup_stored_receipt_binding_receipt(_p78())

    assert first == second
    assert first.evidence_state == EVIDENCE_STATE
    assert first.p78_evidence_state == P78_EVIDENCE_STATE
    assert first.sequence == 7
    assert first.canonical_receipt_verified is True
    assert first.exact_payload_identity_verified is True
    assert first.automatic_control_allowed is False
    assert first.binding_receipt_payload_size_bytes == len(first.binding_receipt_payload_utf8)
    assert first.binding_receipt_payload_sha256 == hashlib.sha256(
        first.binding_receipt_payload_utf8
    ).hexdigest()

    decoded = json.loads(first.binding_receipt_payload_utf8.decode("utf-8"))
    assert decoded == {
        "admission_binding_sha256": "c" * 64,
        "lineage_sha256": "a" * 64,
        "p78_evidence_state": P78_EVIDENCE_STATE,
        "receipt_identity_binding_sha256": "e" * 64,
        "receipt_payload_sha256": "b" * 64,
        "receipt_payload_size_bytes": 321,
        "sequence": 7,
        "stored_identity_payload_sha256": "d" * 64,
        "stored_identity_payload_size_bytes": 256,
    }
    assert first.binding_receipt_payload_utf8 == json.dumps(
        decoded, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


@pytest.mark.parametrize(
    "mutation",
    [
        {"evidence_state": "WRONG"},
        {"automatic_control_allowed": True},
        {"p75_contract_verified": False},
        {"p77_contract_verified": False},
        {"cross_evidence_identity_verified": False},
        {"sequence": True},
        {"sequence": 0},
        {"lineage_sha256": "A" * 64},
        {"receipt_payload_sha256": "g" * 64},
        {"receipt_payload_size_bytes": 0},
        {"admission_binding_sha256": "0" * 63},
        {"stored_identity_payload_sha256": "f" * 63},
        {"stored_identity_payload_size_bytes": 0},
        {"receipt_identity_binding_sha256": "Z" * 64},
    ],
)
def test_p79_rejects_incompatible_or_weakened_p78_evidence(mutation) -> None:
    with pytest.raises(ValueError):
        encode_recovery_startup_stored_receipt_binding_receipt(
            replace(_p78(), **mutation)
        )


def test_p79_rejects_non_p78_object() -> None:
    with pytest.raises(ValueError, match="P78"):
        encode_recovery_startup_stored_receipt_binding_receipt(
            object()  # type: ignore[arg-type]
        )


def test_p79_receipt_identity_changes_with_each_bound_identity() -> None:
    baseline = encode_recovery_startup_stored_receipt_binding_receipt(_p78())

    mutations = [
        {"sequence": 8},
        {"lineage_sha256": "1" * 64},
        {"receipt_payload_sha256": "2" * 64},
        {"receipt_payload_size_bytes": 322},
        {"admission_binding_sha256": "3" * 64},
        {"stored_identity_payload_sha256": "4" * 64},
        {"stored_identity_payload_size_bytes": 257},
        {"receipt_identity_binding_sha256": "5" * 64},
    ]

    for mutation in mutations:
        changed = encode_recovery_startup_stored_receipt_binding_receipt(
            replace(_p78(), **mutation)
        )
        assert changed.binding_receipt_payload_sha256 != baseline.binding_receipt_payload_sha256
        assert changed.binding_receipt_payload_utf8 != baseline.binding_receipt_payload_utf8


def test_p79_is_portable_evidence_not_freshness_or_startup_authority() -> None:
    evidence = encode_recovery_startup_stored_receipt_binding_receipt(_p78())

    assert evidence.automatic_control_allowed is False
    assert "freshness" in TRUTH_BOUNDARY
    assert "coordinated rollback or replay" in TRUTH_BOUNDARY
    assert "authorize startup" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark" in TRUTH_BOUNDARY
    assert "novelty" in TRUTH_BOUNDARY
