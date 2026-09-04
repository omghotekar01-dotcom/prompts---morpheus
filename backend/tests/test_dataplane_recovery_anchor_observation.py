from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.dataplane import VersionedArtifactRouter
from app.dataplane_recovery import capture_active_route_checkpoint
from app.dataplane_recovery_anchor import verify_recovery_expected_head
from app.dataplane_recovery_anchor_observation import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    verify_recovery_expected_head_post_release,
)
from app.dataplane_recovery_anchor_ownership import advance_recovery_expected_head_ownership_bound
from app.dataplane_recovery_anchor_rebootstrap import verify_recovery_against_stored_expected_head
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


def _p70(tmp_path: Path):
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
    p70 = advance_recovery_expected_head_ownership_bound(anchor_path, anchor_store, p67)
    return anchor_path, p70


def test_p71_verifies_exact_unlocked_post_release_anchor(tmp_path: Path) -> None:
    anchor_path, p70 = _p70(tmp_path)

    evidence = verify_recovery_expected_head_post_release(anchor_path, p70)

    assert evidence.sequence == p70.sequence == 2
    assert evidence.lineage_sha256 == p70.lineage_sha256
    assert evidence.anchor_payload_sha256 == p70.anchor_payload_sha256
    assert evidence.anchor_payload_size_bytes == p70.anchor_payload_size_bytes
    assert evidence.lock_path == p70.lock_path
    assert evidence.lock_absent_when_observed is True
    assert evidence.exact_byte_identity_verified is True
    assert evidence.canonical_semantics_verified is True
    assert evidence.evidence_state == EVIDENCE_STATE
    assert evidence.automatic_control_allowed is False
    assert evidence.as_dict()["truth_boundary"] == TRUTH_BOUNDARY


def test_p71_rejects_anchor_drift_after_p70_release(tmp_path: Path) -> None:
    anchor_path, p70 = _p70(tmp_path)
    anchor_path.write_bytes(anchor_path.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="byte length"):
        verify_recovery_expected_head_post_release(anchor_path, p70)


def test_p71_rejects_same_size_anchor_hash_drift(tmp_path: Path) -> None:
    anchor_path, p70 = _p70(tmp_path)
    payload = bytearray(anchor_path.read_bytes())
    payload[-2] = ord("0") if payload[-2] != ord("0") else ord("1")
    anchor_path.write_bytes(bytes(payload))

    with pytest.raises(ValueError, match="SHA-256"):
        verify_recovery_expected_head_post_release(anchor_path, p70)


def test_p71_fails_when_cooperative_lock_is_present_again(tmp_path: Path) -> None:
    anchor_path, p70 = _p70(tmp_path)
    lock = Path(p70.lock_path)
    lock.write_bytes(b"another-cooperating-writer\n")

    with pytest.raises(RuntimeError, match="lock path present"):
        verify_recovery_expected_head_post_release(anchor_path, p70)

    assert lock.read_bytes() == b"another-cooperating-writer\n"


def test_p71_rejects_weakened_or_incompatible_p70_evidence(tmp_path: Path) -> None:
    anchor_path, p70 = _p70(tmp_path)

    weakened = replace(p70, ownership_bound_release_verified=False)
    with pytest.raises(ValueError, match="ownership-bound release"):
        verify_recovery_expected_head_post_release(anchor_path, weakened)

    incompatible = replace(p70, evidence_state="NOT_P70")
    with pytest.raises(ValueError, match="incompatible evidence state"):
        verify_recovery_expected_head_post_release(anchor_path, incompatible)

    escalated = replace(p70, automatic_control_allowed=True)
    with pytest.raises(ValueError, match="automatic control"):
        verify_recovery_expected_head_post_release(anchor_path, escalated)


def test_p71_rejects_semantic_identity_drift_even_if_caller_forges_byte_fields(tmp_path: Path) -> None:
    anchor_path, p70 = _p70(tmp_path)
    forged = replace(p70, sequence=p70.sequence + 1)

    with pytest.raises(ValueError, match="sequence"):
        verify_recovery_expected_head_post_release(anchor_path, forged)


def test_p71_truth_boundary_is_snapshot_only_not_future_stability(tmp_path: Path) -> None:
    anchor_path, p70 = _p70(tmp_path)
    evidence = verify_recovery_expected_head_post_release(anchor_path, p70)
    assert evidence.exact_byte_identity_verified is True

    # A later change is outside P71's observation window; the old evidence is not a lease.
    anchor_path.write_bytes(anchor_path.read_bytes() + b"\n")
    assert anchor_path.stat().st_size != evidence.anchor_payload_size_bytes
    assert "another writer may acquire the lock or replace the anchor immediately afterward" in TRUTH_BOUNDARY
