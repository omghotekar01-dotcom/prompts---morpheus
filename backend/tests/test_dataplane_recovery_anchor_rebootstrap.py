from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.dataplane import VersionedArtifactRouter
from app.dataplane_recovery import capture_active_route_checkpoint
from app.dataplane_recovery_anchor import verify_recovery_expected_head
from app.dataplane_recovery_anchor_rebootstrap import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    verify_recovery_against_stored_expected_head,
)
from app.dataplane_recovery_anchor_store import publish_recovery_expected_head
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


def _predecessor_and_anchor(tmp_path: Path):
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
    return first, predecessor, anchor_path, anchor_store


def _current(tmp_path: Path, predecessor, *, name: str = "second", candidate: str = "candidate-c", artifact: str = "c"):
    current = _published(tmp_path, name, candidate, artifact)
    lineage = verify_recovery_lineage(*current, predecessor=predecessor)
    return current, lineage


def test_p67_binds_exact_stored_anchor_to_current_recovery(tmp_path: Path) -> None:
    _, predecessor, anchor_path, anchor_store = _predecessor_and_anchor(tmp_path)
    current, lineage = _current(tmp_path, predecessor)

    evidence = verify_recovery_against_stored_expected_head(
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

    assert evidence.sequence == 2
    assert evidence.lineage_sha256 == lineage.lineage_sha256
    assert evidence.predecessor_sequence == predecessor.sequence == 1
    assert evidence.predecessor_lineage_sha256 == predecessor.lineage_sha256
    assert evidence.anchor_payload_sha256 == anchor_store.anchor_payload_sha256
    assert evidence.anchor_payload_size_bytes == anchor_store.anchor_payload_size_bytes
    assert evidence.stored_anchor_identity_verified is True
    assert evidence.predecessor_anchor_match_verified is True
    assert evidence.exact_p65_recomputation_verified is True
    assert evidence.stored_head_recovery_consistency_verified is True
    assert evidence.evidence_state == EVIDENCE_STATE
    assert evidence.automatic_control_allowed is False
    assert len(evidence.binding_sha256) == 64
    assert evidence.as_dict()["truth_boundary"] == TRUTH_BOUNDARY

    repeated = verify_recovery_against_stored_expected_head(
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
    assert repeated == evidence


def test_p67_rejects_tampered_stored_anchor_bytes(tmp_path: Path) -> None:
    _, predecessor, anchor_path, anchor_store = _predecessor_and_anchor(tmp_path)
    current, lineage = _current(tmp_path, predecessor)
    anchor_path.write_bytes(anchor_path.read_bytes() + b"\n")

    with pytest.raises(ValueError):
        verify_recovery_against_stored_expected_head(
            current[0], anchor_path, current[1], current[2], current[3], current[4],
            lineage, predecessor, anchor_store
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_state", "WRONG"),
        ("canonical_anchor_verified", False),
        ("same_directory_replace_used", False),
        ("readback_identity_verified", False),
        ("store_consistency_verified", False),
        ("p65_evidence_state", "WRONG"),
        ("automatic_control_allowed", True),
        ("sequence", True),
        ("lineage_sha256", "A" * 64),
        ("anchor_payload_sha256", "0" * 63),
        ("anchor_payload_size_bytes", 0),
    ],
)
def test_p67_rejects_incompatible_or_drifted_p66_evidence(
    tmp_path: Path, field: str, value: object
) -> None:
    _, predecessor, anchor_path, anchor_store = _predecessor_and_anchor(tmp_path)
    current, lineage = _current(tmp_path, predecessor)
    forged = replace(anchor_store, **{field: value})

    with pytest.raises(ValueError):
        verify_recovery_against_stored_expected_head(
            current[0], anchor_path, current[1], current[2], current[3], current[4],
            lineage, predecessor, forged
        )


def test_p67_rejects_predecessor_that_does_not_match_stored_head(tmp_path: Path) -> None:
    _, predecessor, anchor_path, anchor_store = _predecessor_and_anchor(tmp_path)
    current, lineage = _current(tmp_path, predecessor)

    other = _published(tmp_path, "other", "candidate-x", "d")
    wrong_predecessor = verify_recovery_lineage(*other)
    assert wrong_predecessor.sequence == predecessor.sequence
    assert wrong_predecessor.lineage_sha256 != predecessor.lineage_sha256

    with pytest.raises(ValueError):
        verify_recovery_against_stored_expected_head(
            current[0], anchor_path, current[1], current[2], current[3], current[4],
            lineage, wrong_predecessor, anchor_store
        )


def test_p67_rejects_current_lineage_drift(tmp_path: Path) -> None:
    _, predecessor, anchor_path, anchor_store = _predecessor_and_anchor(tmp_path)
    current, lineage = _current(tmp_path, predecessor)
    forged = replace(lineage, lineage_sha256="0" * 64)

    with pytest.raises(ValueError):
        verify_recovery_against_stored_expected_head(
            current[0], anchor_path, current[1], current[2], current[3], current[4],
            forged, predecessor, anchor_store
        )


def test_p67_truth_boundary_does_not_claim_latest_or_rollback_prevention(tmp_path: Path) -> None:
    _, predecessor, anchor_path, anchor_store = _predecessor_and_anchor(tmp_path)

    # A separate internally valid sequence-2 descendant may already exist, but P67 has no
    # independently trusted latest-head source with which to discover that fact.
    ignored_newer, ignored_lineage = _current(
        tmp_path, predecessor, name="ignored-newer", candidate="candidate-newer", artifact="d"
    )
    assert ignored_lineage.sequence == 2
    assert ignored_newer[0].exists()

    branch, branch_lineage = _current(
        tmp_path, predecessor, name="branch", candidate="candidate-branch", artifact="e"
    )
    verified = verify_recovery_against_stored_expected_head(
        branch[0],
        anchor_path,
        branch[1],
        branch[2],
        branch[3],
        branch[4],
        branch_lineage,
        predecessor,
        anchor_store,
    )
    assert verified.stored_head_recovery_consistency_verified is True
    assert "coordinated rollback" in TRUTH_BOUNDARY.casefold()
    assert "latest" in TRUTH_BOUNDARY.casefold()
