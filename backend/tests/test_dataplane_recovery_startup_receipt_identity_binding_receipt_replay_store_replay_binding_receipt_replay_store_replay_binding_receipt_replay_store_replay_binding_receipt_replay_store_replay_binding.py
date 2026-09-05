from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay import (
    EVIDENCE_STATE as P95_EVIDENCE_STATE,
    RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayEvidence,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay import (
    EVIDENCE_STATE as P97_EVIDENCE_STATE,
    RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoreReplayEvidence,
)
from app.dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    bind_recovery_startup_replayed_receipt_to_retained_replay_identity,
)

FIELDS = (
    ("sequence", "int"),
    ("lineage_sha256", "sha"),
    ("binding_receipt_payload_sha256", "sha"),
    ("binding_receipt_payload_size_bytes", "int"),
    ("receipt_identity_binding_sha256", "sha"),
    ("retained_identity_payload_sha256", "sha"),
    ("retained_identity_payload_size_bytes", "int"),
    ("replay_stored_identity_binding_sha256", "sha"),
    ("replay_binding_receipt_payload_sha256", "sha"),
    ("replay_binding_receipt_payload_size_bytes", "int"),
    ("retained_replay_identity_payload_sha256", "sha"),
    ("retained_replay_identity_payload_size_bytes", "int"),
    ("replay_retained_identity_binding_sha256", "sha"),
    ("replay_retained_identity_binding_receipt_payload_sha256", "sha"),
    ("replay_retained_identity_binding_receipt_payload_size_bytes", "int"),
    ("retained_replay_receipt_identity_payload_sha256", "sha"),
    ("retained_replay_receipt_identity_payload_size_bytes", "int"),
    ("replay_retained_receipt_identity_binding_sha256", "sha"),
    ("replay_retained_receipt_identity_binding_receipt_payload_sha256", "sha"),
    ("replay_retained_receipt_identity_binding_receipt_payload_size_bytes", "int"),
)


def _canonical_sha(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _fixtures():
    values = {}
    sha_i = 0
    int_i = 101
    for field, kind in FIELDS:
        if kind == "sha":
            sha_i += 1
            values[field] = hashlib.sha256(f"shared-{sha_i}".encode()).hexdigest()
        else:
            values[field] = 7 if field == "sequence" else int_i
            int_i += 1

    p95 = RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayEvidence(
        **values,
        expected_payload_identity_verified=True,
        canonical_receipt_verified=True,
        dependency_state_verified=True,
        replay_retained_receipt_identity_binding_recomputed_verified=True,
        p93_evidence_state="p93-compatible",
    )
    retained_sha = hashlib.sha256(b"retained-p96-record").hexdigest()
    retained_size = 777
    p97 = RecoveryStartupReplayRetainedReceiptIdentityBindingReceiptReplayIdentityStoreReplayEvidence(
        **values,
        stored_payload_sha256=retained_sha,
        stored_payload_size_bytes=retained_size,
        source_path="/tmp/p96.json",
        p96_evidence_state_verified=True,
        p96_verification_flags_verified=True,
        exact_payload_identity_verified=True,
        canonical_record_verified=True,
        semantic_agreement_verified=True,
    )
    return p95, p97, values, retained_sha, retained_size


def test_p98_binds_matching_p95_p97_deterministically():
    p95, p97, values, retained_sha, retained_size = _fixtures()
    first = bind_recovery_startup_replayed_receipt_to_retained_replay_identity(p95, p97)
    second = bind_recovery_startup_replayed_receipt_to_retained_replay_identity(p95, p97)
    expected = _canonical_sha({
        **values,
        "retained_replayed_receipt_identity_payload_sha256": retained_sha,
        "retained_replayed_receipt_identity_payload_size_bytes": retained_size,
        "p95_evidence_state": P95_EVIDENCE_STATE,
        "p97_evidence_state": P97_EVIDENCE_STATE,
    })
    assert first == second
    assert first.replayed_receipt_retained_identity_binding_sha256 == expected
    assert first.retained_replayed_receipt_identity_payload_sha256 == retained_sha
    assert first.retained_replayed_receipt_identity_payload_size_bytes == retained_size
    assert first.p95_contract_verified is True
    assert first.p97_contract_verified is True
    assert first.cross_evidence_identity_verified is True
    assert first.evidence_state == EVIDENCE_STATE
    assert first.automatic_control_allowed is False


@pytest.mark.parametrize("field,kind", FIELDS)
def test_p98_rejects_every_shared_identity_mismatch(field, kind):
    p95, p97, _, _, _ = _fixtures()
    changed = hashlib.sha256((field + "-other").encode()).hexdigest() if kind == "sha" else getattr(p97, field) + 1
    with pytest.raises(ValueError, match=f"P95/P97 {field} mismatch"):
        bind_recovery_startup_replayed_receipt_to_retained_replay_identity(
            p95, replace(p97, **{field: changed})
        )


@pytest.mark.parametrize(
    "flag",
    [
        "expected_payload_identity_verified",
        "canonical_receipt_verified",
        "dependency_state_verified",
        "replay_retained_receipt_identity_binding_recomputed_verified",
    ],
)
def test_p98_rejects_weakened_p95_contract(flag):
    p95, p97, _, _, _ = _fixtures()
    with pytest.raises(ValueError, match="P95 verification flags"):
        bind_recovery_startup_replayed_receipt_to_retained_replay_identity(
            replace(p95, **{flag: False}), p97
        )


@pytest.mark.parametrize(
    "flag",
    [
        "p96_evidence_state_verified",
        "p96_verification_flags_verified",
        "exact_payload_identity_verified",
        "canonical_record_verified",
        "semantic_agreement_verified",
    ],
)
def test_p98_rejects_weakened_p97_contract(flag):
    p95, p97, _, _, _ = _fixtures()
    with pytest.raises(ValueError, match="P97 verification flags"):
        bind_recovery_startup_replayed_receipt_to_retained_replay_identity(
            p95, replace(p97, **{flag: False})
        )


def test_p98_rejects_state_drift_and_control_escalation():
    p95, p97, _, _, _ = _fixtures()
    with pytest.raises(ValueError, match="P95 evidence state"):
        bind_recovery_startup_replayed_receipt_to_retained_replay_identity(
            replace(p95, evidence_state="drift"), p97
        )
    with pytest.raises(ValueError, match="P97 evidence state"):
        bind_recovery_startup_replayed_receipt_to_retained_replay_identity(
            p95, replace(p97, evidence_state="drift")
        )
    with pytest.raises(ValueError, match="P95 evidence must not grant automatic-control"):
        bind_recovery_startup_replayed_receipt_to_retained_replay_identity(
            replace(p95, automatic_control_allowed=True), p97
        )
    with pytest.raises(ValueError, match="P97 evidence must not grant automatic-control"):
        bind_recovery_startup_replayed_receipt_to_retained_replay_identity(
            p95, replace(p97, automatic_control_allowed=True)
        )


@pytest.mark.parametrize("bad", [0, -1, True])
def test_p98_rejects_invalid_positive_integer_identity(bad):
    p95, p97, _, _, _ = _fixtures()
    with pytest.raises(ValueError, match="positive integer"):
        bind_recovery_startup_replayed_receipt_to_retained_replay_identity(
            replace(p95, sequence=bad), p97
        )


def test_p98_rejects_malformed_sha_identity():
    p95, p97, _, _, _ = _fixtures()
    with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
        bind_recovery_startup_replayed_receipt_to_retained_replay_identity(
            replace(p95, lineage_sha256="A" * 64), p97
        )


@pytest.mark.parametrize("field,value", [
    ("stored_payload_sha256", "A" * 64),
    ("stored_payload_size_bytes", 0),
    ("stored_payload_size_bytes", True),
])
def test_p98_rejects_invalid_retained_p96_record_identity(field, value):
    p95, p97, _, _, _ = _fixtures()
    expected = "64 lowercase hexadecimal" if field.endswith("sha256") else "positive integer"
    with pytest.raises(ValueError, match=expected):
        bind_recovery_startup_replayed_receipt_to_retained_replay_identity(
            p95, replace(p97, **{field: value})
        )


def test_p98_binding_is_sensitive_to_retained_p96_record_identity():
    p95, p97, _, _, _ = _fixtures()
    original = bind_recovery_startup_replayed_receipt_to_retained_replay_identity(p95, p97)
    changed_sha = replace(p97, stored_payload_sha256=hashlib.sha256(b"other-retained-p96").hexdigest())
    changed_size = replace(p97, stored_payload_size_bytes=p97.stored_payload_size_bytes + 1)
    assert (
        bind_recovery_startup_replayed_receipt_to_retained_replay_identity(p95, changed_sha)
        .replayed_receipt_retained_identity_binding_sha256
        != original.replayed_receipt_retained_identity_binding_sha256
    )
    assert (
        bind_recovery_startup_replayed_receipt_to_retained_replay_identity(p95, changed_size)
        .replayed_receipt_retained_identity_binding_sha256
        != original.replayed_receipt_retained_identity_binding_sha256
    )


def test_p98_binding_commits_to_dependency_evidence_states():
    p95, p97, values, retained_sha, retained_size = _fixtures()
    result = bind_recovery_startup_replayed_receipt_to_retained_replay_identity(p95, p97)
    without_states = _canonical_sha({
        **values,
        "retained_replayed_receipt_identity_payload_sha256": retained_sha,
        "retained_replayed_receipt_identity_payload_size_bytes": retained_size,
    })
    assert result.replayed_receipt_retained_identity_binding_sha256 != without_states


def test_p98_rejects_incompatible_input_types():
    p95, p97, _, _, _ = _fixtures()
    with pytest.raises(ValueError, match="P95.*incompatible type"):
        bind_recovery_startup_replayed_receipt_to_retained_replay_identity(object(), p97)
    with pytest.raises(ValueError, match="P97.*incompatible type"):
        bind_recovery_startup_replayed_receipt_to_retained_replay_identity(p95, object())


def test_p98_truth_boundary_is_explicit_and_non_authoritative():
    p95, p97, _, _, _ = _fixtures()
    result = bind_recovery_startup_replayed_receipt_to_retained_replay_identity(p95, p97)
    rendered = result.as_dict()
    assert rendered["truth_boundary"] == TRUTH_BOUNDARY
    assert "read-only composition gate" in TRUTH_BOUNDARY
    assert "does not authenticate" in TRUTH_BOUNDARY
    assert "freshness/latest/global/monotonic" in TRUTH_BOUNDARY
    assert "production readiness" in TRUTH_BOUNDARY
    assert "benchmark evidence" in TRUTH_BOUNDARY
    assert "novelty evidence" in TRUTH_BOUNDARY
    assert rendered["automatic_control_allowed"] is False
