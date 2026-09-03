from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.dataplane import VersionedArtifactRouter
from app.dataplane_recovery import capture_active_route_checkpoint
from app.dataplane_recovery_anchor import verify_recovery_expected_head
from app.dataplane_recovery_anchor_advance import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    advance_recovery_expected_head,
)
from app.dataplane_recovery_anchor_rebootstrap import verify_recovery_against_stored_expected_head
from app.dataplane_recovery_anchor_store import load_recovery_expected_head, publish_recovery_expected_head
from app.dataplane_recovery_generation import verify_recovery_generation_semantics
from app.dataplane_recovery_interchange import export_recovery_checkpoint
from app.dataplane_recovery_lineage import GENESIS_PREDECESSOR_SHA256, verify_recovery_lineage
from app.dataplane_recovery_store import publish_recovery_payload
from app.dataplane_recovery_store_rebootstrap import verify_rebootstrap_from_store


def _published(tmp_path: Path, name: str, candidate: str, artifact_char: str):
    source = VersionedArtifactRouter()
    source.bootstrap(
        "dep-a",
        candidate_id=candidate,
        artifact_sha256=artifact_char * 64,
        verification_manifest_sha256="b" * 64,
    )
    checkpoint = capture_active_route_checkpoint(source)
    payload = export_recovery_checkpoint(checkpoint)
    target = tmp_path / f"{name}.json"
    store = publish_recovery_payload(target, payload)

    recovered = VersionedArtifactRouter()
    recovered.bootstrap(
        "dep-a",
        candidate_id=candidate,
        artifact_sha256=artifact_char * 64,
        verification_manifest_sha256="b" * 64,
    )
    p62 = verify_rebootstrap_from_store(target, recovered, store)
    p63 = verify_recovery_generation_semantics(target, recovered, store, p62)
    return target, recovered, store, p62, p63


def _verified_successor(tmp_path: Path):
    first = _published(tmp_path, "first", "candidate-a", "a")
    predecessor = verify_recovery_lineage(*first)
    p65 = verify_recovery_expected_head(
        *first,
        predecessor,
        expected_predecessor_sequence=0,
        expected_predecessor_lineage_sha256=GENESIS_PREDECESSOR_SHA256,
    )
    anchor_path = tmp_path / "expected-head.json"
    anchor_store = publish_recovery_expected_head(anchor_path, p65)

    current = _published(tmp_path, "second", "candidate-c", "c")
    lineage = verify_recovery_lineage(*current, predecessor=predecessor)
    p67 = verify_recovery_against_stored_expected_head(
        current[0],
        anchor_path,
        current[1],
        current[2],
        current[3],
        current[4],
        lineage,
        predecessor,
        anchor_store,
    )
    return anchor_path, anchor_store, p67


def test_p68_advances_exact_predecessor_to_p67_current_head(tmp_path: Path) -> None:
    anchor_path, anchor_store, p67 = _verified_successor(tmp_path)

    evidence = advance_recovery_expected_head(anchor_path, anchor_store, p67)

    assert evidence.predecessor_sequence == 1
    assert evidence.predecessor_lineage_sha256 == anchor_store.lineage_sha256
    assert evidence.predecessor_payload_sha256 == anchor_store.anchor_payload_sha256
    assert evidence.predecessor_payload_size_bytes == anchor_store.anchor_payload_size_bytes
    assert evidence.sequence == p67.sequence == 2
    assert evidence.lineage_sha256 == p67.lineage_sha256
    assert evidence.predecessor_identity_rechecked is True
    assert evidence.exact_p67_successor_bound is True
    assert evidence.canonical_anchor_verified is True
    assert evidence.same_directory_replace_used is True
    assert evidence.readback_identity_verified is True
    assert evidence.advancement_consistency_verified is True
    assert evidence.evidence_state == EVIDENCE_STATE
    assert evidence.automatic_control_allowed is False
    assert evidence.as_dict()["truth_boundary"] == TRUTH_BOUNDARY

    stored = load_recovery_expected_head(
        anchor_path, expected_payload_sha256=evidence.anchor_payload_sha256
    )
    assert stored.sequence == 2
    assert stored.lineage_sha256 == p67.lineage_sha256
    assert not list(tmp_path.glob(".*.morpheus-head-advance-tmp-*"))


def test_p68_rejects_predecessor_bytes_changed_after_p67_verification(tmp_path: Path) -> None:
    anchor_path, anchor_store, p67 = _verified_successor(tmp_path)
    anchor_path.write_bytes(anchor_path.read_bytes() + b"\n")

    with pytest.raises(ValueError):
        advance_recovery_expected_head(anchor_path, anchor_store, p67)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_state", "WRONG"),
        ("canonical_anchor_verified", False),
        ("same_directory_replace_used", False),
        ("readback_identity_verified", False),
        ("store_consistency_verified", False),
        ("automatic_control_allowed", True),
        ("sequence", True),
        ("lineage_sha256", "A" * 64),
        ("anchor_payload_sha256", "0" * 63),
        ("anchor_payload_size_bytes", 0),
    ],
)
def test_p68_rejects_incompatible_p66_predecessor_evidence(
    tmp_path: Path, field: str, value: object
) -> None:
    anchor_path, anchor_store, p67 = _verified_successor(tmp_path)
    forged = replace(anchor_store, **{field: value})

    with pytest.raises(ValueError):
        advance_recovery_expected_head(anchor_path, forged, p67)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_state", "WRONG"),
        ("stored_anchor_identity_verified", False),
        ("predecessor_anchor_match_verified", False),
        ("exact_p65_recomputation_verified", False),
        ("stored_head_recovery_consistency_verified", False),
        ("automatic_control_allowed", True),
        ("sequence", True),
        ("lineage_sha256", "A" * 64),
        ("predecessor_sequence", 2),
        ("predecessor_lineage_sha256", "0" * 64),
        ("anchor_payload_sha256", "0" * 64),
        ("anchor_payload_size_bytes", 1),
    ],
)
def test_p68_rejects_incompatible_or_drifted_p67_evidence(
    tmp_path: Path, field: str, value: object
) -> None:
    anchor_path, anchor_store, p67 = _verified_successor(tmp_path)
    forged = replace(p67, **{field: value})

    with pytest.raises(ValueError):
        advance_recovery_expected_head(anchor_path, anchor_store, forged)


def test_p68_rejects_non_successor_sequence_even_with_other_fields_consistent(tmp_path: Path) -> None:
    anchor_path, anchor_store, p67 = _verified_successor(tmp_path)
    forged = replace(p67, sequence=3)

    with pytest.raises(ValueError, match="exactly one"):
        advance_recovery_expected_head(anchor_path, anchor_store, forged)


def test_p68_truth_boundary_does_not_claim_cas_or_rollback_resistance(tmp_path: Path) -> None:
    anchor_path, anchor_store, p67 = _verified_successor(tmp_path)
    evidence = advance_recovery_expected_head(anchor_path, anchor_store, p67)

    assert evidence.advancement_consistency_verified is True
    boundary = TRUTH_BOUNDARY.casefold()
    assert "not a concurrency-safe" in boundary
    assert "race" in boundary
    assert "rollback resistant" in boundary
