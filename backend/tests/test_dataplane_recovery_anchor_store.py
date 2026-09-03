from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.dataplane_recovery_anchor import EVIDENCE_STATE as P65_EVIDENCE_STATE
from app.dataplane_recovery_anchor import RecoveryExpectedHeadEvidence
from app.dataplane_recovery_anchor_store import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    load_recovery_expected_head,
    publish_recovery_expected_head,
)


def _p65(*, sequence: int = 7, lineage: str = "a" * 64) -> RecoveryExpectedHeadEvidence:
    return RecoveryExpectedHeadEvidence(
        sequence=sequence,
        lineage_sha256=lineage,
        expected_predecessor_sequence=sequence - 1,
        expected_predecessor_lineage_sha256="b" * 64,
        exact_p64_recomputation_verified=True,
        expected_head_extension_verified=True,
        p64_evidence_state="LOCAL_DATA_PLANE_RECOVERY_LINEAGE_CONSISTENCY_VERIFIED",
    )


def test_p66_publishes_and_loads_strict_canonical_head(tmp_path: Path) -> None:
    target = tmp_path / "anchor.json"
    evidence = publish_recovery_expected_head(target, _p65())

    expected = b'{"lineage_sha256":"' + (b"a" * 64) + b'","sequence":7}'
    assert target.read_bytes() == expected
    assert evidence.sequence == 7
    assert evidence.lineage_sha256 == "a" * 64
    assert evidence.anchor_payload_size_bytes == len(expected)
    assert evidence.canonical_anchor_verified is True
    assert evidence.same_directory_replace_used is True
    assert evidence.readback_identity_verified is True
    assert evidence.store_consistency_verified is True
    assert evidence.p65_evidence_state == P65_EVIDENCE_STATE
    assert evidence.evidence_state == EVIDENCE_STATE
    assert evidence.automatic_control_allowed is False
    assert evidence.as_dict()["truth_boundary"] == TRUTH_BOUNDARY

    loaded = load_recovery_expected_head(target, expected_payload_sha256=evidence.anchor_payload_sha256)
    assert loaded.sequence == 7
    assert loaded.lineage_sha256 == "a" * 64
    assert loaded.as_dict() == {"sequence": 7, "lineage_sha256": "a" * 64}


def test_p66_replaces_existing_head_without_temporary_residue(tmp_path: Path) -> None:
    target = tmp_path / "anchor.json"
    first = publish_recovery_expected_head(target, _p65(sequence=2, lineage="c" * 64))
    second = publish_recovery_expected_head(target, _p65(sequence=3, lineage="d" * 64))

    assert first.anchor_payload_sha256 != second.anchor_payload_sha256
    assert load_recovery_expected_head(target).sequence == 3
    assert load_recovery_expected_head(target).lineage_sha256 == "d" * 64
    assert list(tmp_path.glob(".*.morpheus-head-tmp-*")) == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_state", "WRONG"),
        ("exact_p64_recomputation_verified", False),
        ("expected_head_extension_verified", False),
        ("automatic_control_allowed", True),
        ("sequence", 0),
        ("sequence", True),
        ("lineage_sha256", "A" * 64),
        ("lineage_sha256", "0" * 63),
    ],
)
def test_p66_rejects_incompatible_or_invalid_p65_evidence(
    tmp_path: Path, field: str, value: object
) -> None:
    forged = replace(_p65(), **{field: value})
    target = tmp_path / "anchor.json"
    with pytest.raises(ValueError):
        publish_recovery_expected_head(target, forged)
    assert not target.exists()


@pytest.mark.parametrize(
    "payload",
    [
        b'{"sequence":7,"lineage_sha256":"' + (b"a" * 64) + b'"}',  # valid values, wrong canonical key order
        b'{"lineage_sha256":"' + (b"a" * 64) + b'", "sequence":7}',  # noncanonical whitespace
        b'{"extra":1,"lineage_sha256":"' + (b"a" * 64) + b'","sequence":7}',
        b'{"lineage_sha256":"' + (b"A" * 64) + b'","sequence":7}',
        b'{"lineage_sha256":"' + (b"a" * 64) + b'","sequence":true}',
        b"not-json",
        b"\xff",
    ],
)
def test_p66_rejects_tampered_or_noncanonical_stored_bytes(tmp_path: Path, payload: bytes) -> None:
    target = tmp_path / "anchor.json"
    target.write_bytes(payload)
    with pytest.raises(ValueError):
        load_recovery_expected_head(target)


def test_p66_rejects_wrong_or_malformed_expected_payload_identity(tmp_path: Path) -> None:
    target = tmp_path / "anchor.json"
    evidence = publish_recovery_expected_head(target, _p65())

    with pytest.raises(ValueError):
        load_recovery_expected_head(target, expected_payload_sha256="f" * 64)
    with pytest.raises(ValueError):
        load_recovery_expected_head(target, expected_payload_sha256="x" * 64)
    with pytest.raises(ValueError):
        load_recovery_expected_head(target, expected_payload_sha256="0" * 63)

    # Normalization is limited to harmless surrounding whitespace/case for the optional
    # expected digest; stored anchor bytes themselves remain strict canonical JSON.
    loaded = load_recovery_expected_head(
        target, expected_payload_sha256=f"  {evidence.anchor_payload_sha256.upper()}  "
    )
    assert loaded.sequence == 7


def test_p66_truth_boundary_does_not_upgrade_local_file_to_trusted_anchor(tmp_path: Path) -> None:
    target = tmp_path / "anchor.json"
    old = publish_recovery_expected_head(target, _p65(sequence=2, lineage="c" * 64))
    publish_recovery_expected_head(target, _p65(sequence=3, lineage="d" * 64))

    # Replacing the local file with an older, independently valid canonical payload remains
    # possible. P66 detects byte identity only when the caller retains an expected digest;
    # it cannot establish that the locally presented head is globally/latest trusted state.
    old_payload = b'{"lineage_sha256":"' + (b"c" * 64) + b'","sequence":2}'
    target.write_bytes(old_payload)
    rolled_back = load_recovery_expected_head(target)
    assert rolled_back.sequence == 2
    with pytest.raises(ValueError):
        load_recovery_expected_head(target, expected_payload_sha256="d" * 64)
    assert old.anchor_payload_sha256 != "d" * 64
    assert "does not independently" in TRUTH_BOUNDARY
    assert "rollback" in TRUTH_BOUNDARY.casefold()
