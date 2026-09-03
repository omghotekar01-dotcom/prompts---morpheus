from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.dataplane import VersionedArtifactRouter
from app.dataplane_recovery import capture_active_route_checkpoint
from app.dataplane_recovery_generation import verify_recovery_generation_semantics
from app.dataplane_recovery_interchange import export_recovery_checkpoint
from app.dataplane_recovery_lineage import (
    EVIDENCE_STATE,
    GENESIS_PREDECESSOR_SHA256,
    TRUTH_BOUNDARY,
    verify_recovery_lineage,
)
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


def test_p64_builds_deterministic_genesis_and_successor_lineage(tmp_path: Path) -> None:
    first = _published(tmp_path, "first", "candidate-a", "a")
    genesis = verify_recovery_lineage(*first)
    assert genesis.sequence == 1
    assert genesis.predecessor_lineage_sha256 == GENESIS_PREDECESSOR_SHA256
    assert genesis.predecessor_consistency_verified is True
    assert genesis.evidence_state == EVIDENCE_STATE
    assert genesis.automatic_control_allowed is False
    assert genesis.as_dict()["truth_boundary"] == TRUTH_BOUNDARY
    assert verify_recovery_lineage(*first) == genesis

    second = _published(tmp_path, "second", "candidate-c", "c")
    successor = verify_recovery_lineage(*second, predecessor=genesis, sequence=2)
    assert successor.sequence == 2
    assert successor.predecessor_lineage_sha256 == genesis.lineage_sha256
    assert successor.checkpoint_sha256 != genesis.checkpoint_sha256
    assert len(successor.lineage_sha256) == 64
    assert verify_recovery_lineage(*second, predecessor=genesis) == successor


@pytest.mark.parametrize("sequence", [0, 1, 3, True])
def test_p64_rejects_nonextending_or_invalid_sequence(tmp_path: Path, sequence: object) -> None:
    first = _published(tmp_path, "first", "candidate-a", "a")
    genesis = verify_recovery_lineage(*first)
    second = _published(tmp_path, "second", "candidate-c", "c")
    with pytest.raises(ValueError):
        verify_recovery_lineage(*second, predecessor=genesis, sequence=sequence)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_state", "WRONG"),
        ("predecessor_consistency_verified", False),
        ("automatic_control_allowed", True),
        ("sequence", 0),
        ("checkpoint_sha256", "0" * 64),
        ("payload_sha256", "0" * 64),
        ("p63_generation_binding_sha256", "0" * 64),
        ("predecessor_lineage_sha256", "f" * 64),
        ("lineage_sha256", "0" * 64),
    ],
)
def test_p64_rejects_forged_predecessor(tmp_path: Path, field: str, value: object) -> None:
    first = _published(tmp_path, "first", "candidate-a", "a")
    genesis = verify_recovery_lineage(*first)
    second = _published(tmp_path, "second", "candidate-c", "c")
    forged = replace(genesis, **{field: value})
    with pytest.raises(ValueError):
        verify_recovery_lineage(*second, predecessor=forged)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_state", "WRONG"),
        ("source_generation_provenance_verified", False),
        ("fresh_bootstrap_generation_verified", False),
        ("automatic_control_allowed", True),
        ("checkpoint_sha256", "0" * 64),
        ("payload_sha256", "0" * 64),
        ("generation_binding_sha256", "0" * 64),
    ],
)
def test_p64_rejects_incompatible_or_drifted_p63_evidence(
    tmp_path: Path, field: str, value: object
) -> None:
    target, recovered, store, p62, p63 = _published(tmp_path, "current", "candidate-a", "a")
    forged = replace(p63, **{field: value})
    with pytest.raises(ValueError):
        verify_recovery_lineage(target, recovered, store, p62, forged)


def test_p64_lineage_detects_rollback_relative_to_newer_trusted_receipt(tmp_path: Path) -> None:
    first = _published(tmp_path, "first", "candidate-a", "a")
    genesis = verify_recovery_lineage(*first)
    second = _published(tmp_path, "second", "candidate-c", "c")
    successor = verify_recovery_lineage(*second, predecessor=genesis)

    # Reusing the older checkpoint after the trusted successor cannot masquerade as
    # the successor itself: it becomes a distinct sequence-3 lineage receipt.
    rolled_back = verify_recovery_lineage(*first, predecessor=successor)
    assert rolled_back.sequence == 3
    assert rolled_back.checkpoint_sha256 == genesis.checkpoint_sha256
    assert rolled_back.lineage_sha256 != successor.lineage_sha256
    assert rolled_back.predecessor_lineage_sha256 == successor.lineage_sha256


def test_p64_preserves_unicode_checkpoint_identity(tmp_path: Path) -> None:
    source = VersionedArtifactRouter()
    source.bootstrap("dep-α", candidate_id="candidate-β", artifact_sha256="a" * 64)
    checkpoint = capture_active_route_checkpoint(source)
    payload = export_recovery_checkpoint(checkpoint)
    target = tmp_path / "unicode.json"
    store = publish_recovery_payload(target, payload)
    recovered = VersionedArtifactRouter()
    recovered.bootstrap("dep-α", candidate_id="candidate-β", artifact_sha256="a" * 64)
    p62 = verify_rebootstrap_from_store(target, recovered, store)
    p63 = verify_recovery_generation_semantics(target, recovered, store, p62)
    lineage = verify_recovery_lineage(target, recovered, store, p62, p63)
    assert lineage.sequence == 1
    assert len(lineage.lineage_sha256) == 64
