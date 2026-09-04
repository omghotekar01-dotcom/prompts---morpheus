from __future__ import annotations

from pathlib import Path

import pytest

from app.dataplane import VersionedArtifactRouter
from app.dataplane_recovery import capture_active_route_checkpoint
from app.dataplane_recovery_anchor import verify_recovery_expected_head
from app.dataplane_recovery_anchor_ownership import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    advance_recovery_expected_head_ownership_bound,
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


def test_p70_advances_and_releases_only_owned_lock(tmp_path: Path) -> None:
    anchor_path, anchor_store, p67 = _verified_successor(tmp_path)

    evidence = advance_recovery_expected_head_ownership_bound(anchor_path, anchor_store, p67)

    assert evidence.sequence == p67.sequence == 2
    assert evidence.lineage_sha256 == p67.lineage_sha256
    assert evidence.predecessor_sequence == anchor_store.sequence == 1
    assert len(evidence.ownership_token_sha256) == 64
    assert evidence.exclusive_create_used is True
    assert evidence.ownership_token_fsynced is True
    assert evidence.p68_executed_under_lock is True
    assert evidence.lock_identity_rechecked is True
    assert evidence.ownership_bound_release_verified is True
    assert evidence.advancement_verified is True
    assert evidence.evidence_state == EVIDENCE_STATE
    assert evidence.automatic_control_allowed is False
    assert evidence.as_dict()["truth_boundary"] == TRUTH_BOUNDARY

    stored = load_recovery_expected_head(
        anchor_path, expected_payload_sha256=evidence.anchor_payload_sha256
    )
    assert stored.sequence == 2
    assert stored.lineage_sha256 == p67.lineage_sha256
    assert not Path(evidence.lock_path).exists()


def test_p70_fails_closed_when_lock_already_exists(tmp_path: Path) -> None:
    anchor_path, anchor_store, p67 = _verified_successor(tmp_path)
    original = anchor_path.read_bytes()
    lock = tmp_path / ".expected-head.json.morpheus-head-advance.lock"
    lock.write_text("existing-owner\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="already exists"):
        advance_recovery_expected_head_ownership_bound(anchor_path, anchor_store, p67)

    assert anchor_path.read_bytes() == original
    assert lock.read_text(encoding="utf-8") == "existing-owner\n"


def test_p70_preserves_replacement_lock_when_identity_changes_after_p68(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.dataplane_recovery_anchor_ownership as p70
    from app.dataplane_recovery_anchor_advance import advance_recovery_expected_head as real_p68

    anchor_path, anchor_store, p67 = _verified_successor(tmp_path)
    lock = tmp_path / ".expected-head.json.morpheus-head-advance.lock"

    def disturbed(*args, **kwargs):
        result = real_p68(*args, **kwargs)
        lock.unlink()
        lock.write_bytes(b"replacement-owner\n")
        return result

    monkeypatch.setattr(p70, "advance_recovery_expected_head", disturbed)

    with pytest.raises(RuntimeError, match="identity changed"):
        p70.advance_recovery_expected_head_ownership_bound(anchor_path, anchor_store, p67)

    # P68 completed before the disturbance was detected; P70 does not fabricate rollback.
    stored = load_recovery_expected_head(anchor_path)
    assert stored.sequence == 2
    assert lock.read_bytes() == b"replacement-owner\n"


def test_p70_cleans_its_own_lock_when_p68_rejects(tmp_path: Path) -> None:
    anchor_path, anchor_store, p67 = _verified_successor(tmp_path)
    lock = tmp_path / "custom.lock"
    anchor_path.write_bytes(anchor_path.read_bytes() + b"\n")

    with pytest.raises(ValueError):
        advance_recovery_expected_head_ownership_bound(
            anchor_path,
            anchor_store,
            p67,
            lock_path=lock,
        )

    assert not lock.exists()


def test_p70_rejects_cross_directory_lock_path(tmp_path: Path) -> None:
    anchor_path, anchor_store, p67 = _verified_successor(tmp_path)
    elsewhere = tmp_path / "locks"
    elsewhere.mkdir()

    with pytest.raises(ValueError, match="same directory"):
        advance_recovery_expected_head_ownership_bound(
            anchor_path,
            anchor_store,
            p67,
            lock_path=elsewhere / "head.lock",
        )


def test_p70_truth_boundary_does_not_overclaim(tmp_path: Path) -> None:
    anchor_path, anchor_store, p67 = _verified_successor(tmp_path)
    evidence = advance_recovery_expected_head_ownership_bound(anchor_path, anchor_store, p67)

    assert evidence.advancement_verified is True
    boundary = TRUTH_BOUNDARY.casefold()
    assert "writers bypassing p70 are not excluded" in boundary
    assert "stale locks are not stolen" in boundary
    assert "cannot roll back" in boundary
    assert "no universal cas" in boundary
    assert "rollback resistance" in boundary
    assert "production readiness" in boundary
