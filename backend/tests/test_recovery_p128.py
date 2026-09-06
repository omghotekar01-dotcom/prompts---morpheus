import hashlib
from dataclasses import replace

import pytest

from app.recovery_p123 import EVIDENCE_STATE as P123_EVIDENCE_STATE
from app.recovery_p125 import EVIDENCE_STATE as P125_EVIDENCE_STATE, RecoveryP124ReplayEvidence
from app.recovery_p126 import _FIELDS
from app.recovery_p127 import EVIDENCE_STATE as P127_EVIDENCE_STATE, RecoveryP125ReplayIdentityVerificationEvidence
from app.recovery_p128 import EVIDENCE_STATE, TRUTH_BOUNDARY, bind_p125_replay_to_p127_retained_identity


INT_FIELDS = {field for field, kind in _FIELDS if kind == "int"}
FIELDS = tuple(field for field, _ in _FIELDS)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _values():
    return {
        field: (index if field in INT_FIELDS else _sha(field))
        for index, field in enumerate(FIELDS, 1)
    }


def _p125(**changes):
    values = _values()
    values.update(changes)
    return RecoveryP124ReplayEvidence(
        **values,
        expected_payload_identity_verified=True,
        canonical_receipt_verified=True,
        dependency_state_verified=True,
        p120_p122_composition_binding_recomputed_verified=True,
        p123_evidence_state=P123_EVIDENCE_STATE,
    )


def _p127(**changes):
    values = _values()
    values.update(changes)
    return RecoveryP125ReplayIdentityVerificationEvidence(
        **values,
        stored_payload_sha256=_sha("stored-p126"),
        stored_payload_size_bytes=777,
        source_path="p125.identity.json",
        exact_size_verified=True,
        exact_sha256_verified=True,
        strict_schema_verified=True,
        canonical_encoding_verified=True,
        retained_identity_verified=True,
        p125_evidence_state_verified=True,
    )


def test_binds_matching_verified_replay_paths_deterministically():
    first = bind_p125_replay_to_p127_retained_identity(_p125(), _p127())
    second = bind_p125_replay_to_p127_retained_identity(_p125(), _p127())
    assert first == second
    assert first.p125_contract_verified is True
    assert first.p127_contract_verified is True
    assert first.cross_evidence_identity_verified is True
    assert first.retained_p126_record_payload_sha256 == _sha("stored-p126")
    assert first.retained_p126_record_payload_size_bytes == 777
    assert first.evidence_state == EVIDENCE_STATE
    assert first.automatic_control_allowed is False


@pytest.mark.parametrize("field", FIELDS)
def test_rejects_disagreement_on_every_shared_identity(field):
    drift = 99999 if field in INT_FIELDS else _sha("drift-" + field)
    with pytest.raises(ValueError, match=f"disagrees on {field}"):
        bind_p125_replay_to_p127_retained_identity(_p125(), _p127(**{field: drift}))


@pytest.mark.parametrize(
    "flag",
    (
        "expected_payload_identity_verified",
        "canonical_receipt_verified",
        "dependency_state_verified",
        "p120_p122_composition_binding_recomputed_verified",
    ),
)
def test_rejects_weakened_p125_contract(flag):
    with pytest.raises(ValueError, match="P125 verification contract is incomplete"):
        bind_p125_replay_to_p127_retained_identity(replace(_p125(), **{flag: False}), _p127())


@pytest.mark.parametrize(
    "flag",
    (
        "exact_size_verified",
        "exact_sha256_verified",
        "strict_schema_verified",
        "canonical_encoding_verified",
        "retained_identity_verified",
        "p125_evidence_state_verified",
    ),
)
def test_rejects_weakened_p127_contract(flag):
    with pytest.raises(ValueError, match="P127 verification contract is incomplete"):
        bind_p125_replay_to_p127_retained_identity(_p125(), replace(_p127(), **{flag: False}))


def test_rejects_dependency_state_or_authority_drift():
    with pytest.raises(ValueError, match="P125 evidence state is incompatible"):
        bind_p125_replay_to_p127_retained_identity(replace(_p125(), evidence_state=P125_EVIDENCE_STATE + "_DRIFT"), _p127())
    with pytest.raises(ValueError, match="embedded P123 evidence state is incompatible"):
        bind_p125_replay_to_p127_retained_identity(replace(_p125(), p123_evidence_state=P123_EVIDENCE_STATE + "_DRIFT"), _p127())
    with pytest.raises(ValueError, match="P127 evidence state is incompatible"):
        bind_p125_replay_to_p127_retained_identity(_p125(), replace(_p127(), evidence_state=P127_EVIDENCE_STATE + "_DRIFT"))
    with pytest.raises(ValueError, match="must not grant automatic-control authority"):
        bind_p125_replay_to_p127_retained_identity(replace(_p125(), automatic_control_allowed=True), _p127())
    with pytest.raises(ValueError, match="must not grant automatic-control authority"):
        bind_p125_replay_to_p127_retained_identity(_p125(), replace(_p127(), automatic_control_allowed=True))


@pytest.mark.parametrize("field", FIELDS)
def test_rejects_invalid_shared_identity_types(field):
    invalid = 0 if field in INT_FIELDS else "BAD"
    with pytest.raises(ValueError):
        bind_p125_replay_to_p127_retained_identity(_p125(**{field: invalid}), _p127(**{field: invalid}))


def test_binding_commits_to_retained_record_identity():
    base = bind_p125_replay_to_p127_retained_identity(_p125(), _p127())
    changed_sha = bind_p125_replay_to_p127_retained_identity(
        _p125(), replace(_p127(), stored_payload_sha256=_sha("other-record"))
    )
    changed_size = bind_p125_replay_to_p127_retained_identity(
        _p125(), replace(_p127(), stored_payload_size_bytes=778)
    )
    assert base.p125_p127_composition_binding_sha256 != changed_sha.p125_p127_composition_binding_sha256
    assert base.p125_p127_composition_binding_sha256 != changed_size.p125_p127_composition_binding_sha256


def test_rejects_malformed_retained_record_identity():
    with pytest.raises(ValueError, match="P127 retained P126 record SHA-256"):
        bind_p125_replay_to_p127_retained_identity(_p125(), replace(_p127(), stored_payload_sha256="BAD"))
    with pytest.raises(ValueError, match="P127 retained P126 record size"):
        bind_p125_replay_to_p127_retained_identity(_p125(), replace(_p127(), stored_payload_size_bytes=0))


def test_rejects_incompatible_evidence_types():
    with pytest.raises(ValueError, match="P125 canonical P124 replay evidence has an incompatible type"):
        bind_p125_replay_to_p127_retained_identity(object(), _p127())
    with pytest.raises(ValueError, match="P127 retained P126 replay evidence has an incompatible type"):
        bind_p125_replay_to_p127_retained_identity(_p125(), object())


def test_truth_boundary_remains_explicitly_non_authoritative():
    rendered = bind_p125_replay_to_p127_retained_identity(_p125(), _p127()).as_dict()
    assert rendered["automatic_control_allowed"] is False
    assert rendered["truth_boundary"] == TRUTH_BOUNDARY
    for phrase in (
        "does not authenticate",
        "freshness/latest/global/monotonic",
        "coordinated rollback/replay",
        "authorize startup or mutation",
        "production readiness",
        "benchmark evidence",
        "novelty evidence",
    ):
        assert phrase in TRUTH_BOUNDARY
