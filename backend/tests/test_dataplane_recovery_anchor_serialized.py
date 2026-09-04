from __future__ import annotations

from pathlib import Path

import pytest

from app.dataplane import VersionedArtifactRouter
from app.dataplane_recovery import capture_active_route_checkpoint
from app.dataplane_recovery_anchor import verify_recovery_expected_head
from app.dataplane_recovery_anchor_rebootstrap import verify_recovery_against_stored_expected_head
from app.dataplane_recovery_anchor_serialized import (
    EVIDENCE_STATE,
    TRUTH_BOUNDARY,
    advance_recovery_expected_head_serialized,
)
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


def test_p69_serializes_one_p68_advancement_and_releases_lock(tmp_path: Path) -> None:
    anchor_path, anchor_store, p67 = _verified_successor(tmp_path)

    evidence = advance_recovery_expected_head_serialized(anchor_path, anchor_store, p67)

    assert evidence.sequence == p67.sequence == 2
    assert evidence.lineage_sha256 == p67.lineage_sha256
    assert evidence.predecessor_sequence == anchor_store.sequence == 1
    assert evidence.predecessor_lineage_sha256 == anchor_store.lineage_sha256
    assert evidence.exclusive_create_used is True
    assert evidence.cooperative_lock_acquired is True
    assert evidence.p68_executed_under_lock is True
    assert evidence.cooperative_lock_released is True
    assert evidence.serialized_advancement_verified is True
    assert evidence.evidence_state == EVIDENCE_STATE
    assert evidence.automatic_control_allowed is False
    assert evidence.as_dict()["truth_boundary"] == TRUTH_BOUNDARY

    stored = load_recovery_expected_head(
        anchor_path, expected_payload_sha256=evidence.anchor_payload_sha256
    )
    assert stored.sequence == 2
    assert stored.lineage_sha256 == p67.lineage_sha256
    assert not Path(evidence.lock_path).exists()


def test_p69_fails_closed_when_cooperative_lock_already_exists(tmp_path: Path) -> None:
    anchor_path, anchor_store, p67 = _verified_successor(tmp_path)
    original = anchor_path.read_bytes()
    lock = tmp_path / ".expected-head.json.morpheus-head-advance.lock"
    lock.write_text("existing-owner\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="already exists"):
        advance_recovery_expected_head_serialized(anchor_path, anchor_store, p67)

    assert anchor_path.read_bytes() == original
    assert lock.read_text(encoding="utf-8") == "existing-owner\n"


def test_p69_does_not_steal_a_stale_lock(tmp_path: Path) -> None:
    anchor_path, anchor_store, p67 = _verified_successor(tmp_path)
    lock = tmp_path / ".expected-head.json.morpheus-head-advance.lock"
    lock.write_text("pid=999999999\n", encoding="ascii")

    with pytest.raises(RuntimeError, match="refusing unsafe lock stealing"):
        advance_recovery_expected_head_serialized(anchor_path, anchor_store, p67)

    assert lock.exists()


def test_p69_requires_same_directory_lock_path(tmp_path: Path) -> None:
    anchor_path, anchor_store, p67 = _verified_successor(tmp_path)
    elsewhere = tmp_path / "locks"
    elsewhere.mkdir()

    with pytest.raises(ValueError, match="same directory"):
        advance_recovery_expected_head_serialized(
            anchor_path,
            anchor_store,
            p67,
            lock_path=elsewhere / "head.lock",
        )


def test_p69_releases_lock_when_p68_rejects_stale_predecessor(tmp_path: Path) -> None:
    anchor_path, anchor_store, p67 = _verified_successor(tmp_path)
    lock = tmp_path / "custom.lock"
    anchor_path.write_bytes(anchor_path.read_bytes() + b"\n")

    with pytest.raises(ValueError):
        advance_recovery_expected_head_serialized(
            anchor_path,
            anchor_store,
            p67,
            lock_path=lock,
        )

    assert not lock.exists()


def test_p69_second_attempt_with_consumed_predecessor_fails_and_cleans_lock(tmp_path: Path) -> None:
    anchor_path, anchor_store, p67 = _verified_successor(tmp_path)
    advance_recovery_expected_head_serialized(anchor_path, anchor_store, p67)
    lock = tmp_path / ".expected-head.json.morpheus-head-advance.lock"

    with pytest.raises(ValueError):
        advance_recovery_expected_head_serialized(anchor_path, anchor_store, p67)

    assert not lock.exists()


def test_p69_truth_boundary_is_cooperative_not_universal_cas(tmp_path: Path) -> None:
    anchor_path, anchor_store, p67 = _verified_successor(tmp_path)
    evidence = advance_recovery_expected_head_serialized(anchor_path, anchor_store, p67)

    assert evidence.serialized_advancement_verified is True
    boundary = TRUTH_BOUNDARY.casefold()
    assert "cooperative" in boundary
    assert "writers that bypass p69 are not excluded" in boundary
    assert "stale lock" in boundary
    assert "not a universal" in boundary
    assert "rollback resistance" in boundary
