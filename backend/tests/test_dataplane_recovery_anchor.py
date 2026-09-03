from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.dataplane import VersionedArtifactRouter
from app.dataplane_recovery import capture_active_route_checkpoint
from app.dataplane_recovery_anchor import EVIDENCE_STATE, TRUTH_BOUNDARY, verify_recovery_expected_head
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


def test_p65_verifies_genesis_and_successor_expected_head(tmp_path: Path) -> None:
    first = _published(tmp_path, "first", "candidate-a", "a")
    genesis = verify_recovery_lineage(*first)
    genesis_anchor = verify_recovery_expected_head(
        *first,
        genesis,
        expected_predecessor_sequence=0,
        expected_predecessor_lineage_sha256=GENESIS_PREDECESSOR_SHA256,
    )
    assert genesis_anchor.sequence == 1
    assert genesis_anchor.expected_predecessor_sequence == 0
    assert genesis_anchor.exact_p64_recomputation_verified is True
    assert genesis_anchor.expected_head_extension_verified is True
    assert genesis_anchor.evidence_state == EVIDENCE_STATE
    assert genesis_anchor.automatic_control_allowed is False
    assert genesis_anchor.as_dict()["truth_boundary"] == TRUTH_BOUNDARY

    second = _published(tmp_path, "second", "candidate-c", "c")
    successor = verify_recovery_lineage(*second, predecessor=genesis)
    anchored = verify_recovery_expected_head(
        *second,
        successor,
        predecessor=genesis,
        expected_predecessor_sequence=genesis.sequence,
        expected_predecessor_lineage_sha256=genesis.lineage_sha256,
    )
    assert anchored.sequence == 2
    assert anchored.lineage_sha256 == successor.lineage_sha256
    assert anchored.expected_predecessor_lineage_sha256 == genesis.lineage_sha256


@pytest.mark.parametrize("value", [-1, True, 1.0, "1"])
def test_p65_rejects_invalid_anchor_sequence(tmp_path: Path, value: object) -> None:
    first = _published(tmp_path, "first", "candidate-a", "a")
    genesis = verify_recovery_lineage(*first)
    with pytest.raises(ValueError):
        verify_recovery_expected_head(
            *first,
            genesis,
            expected_predecessor_sequence=value,  # type: ignore[arg-type]
            expected_predecessor_lineage_sha256=GENESIS_PREDECESSOR_SHA256,
        )


@pytest.mark.parametrize("value", ["0" * 63, "G" * 64, "A" * 64, 123])
def test_p65_rejects_invalid_anchor_hash(tmp_path: Path, value: object) -> None:
    first = _published(tmp_path, "first", "candidate-a", "a")
    genesis = verify_recovery_lineage(*first)
    with pytest.raises(ValueError):
        verify_recovery_expected_head(
            *first,
            genesis,
            expected_predecessor_sequence=0,
            expected_predecessor_lineage_sha256=value,  # type: ignore[arg-type]
        )


def test_p65_rejects_stale_or_wrong_expected_head(tmp_path: Path) -> None:
    first = _published(tmp_path, "first", "candidate-a", "a")
    genesis = verify_recovery_lineage(*first)
    second = _published(tmp_path, "second", "candidate-c", "c")
    successor = verify_recovery_lineage(*second, predecessor=genesis)

    with pytest.raises(ValueError):
        verify_recovery_expected_head(
            *second,
            successor,
            predecessor=genesis,
            expected_predecessor_sequence=0,
            expected_predecessor_lineage_sha256=GENESIS_PREDECESSOR_SHA256,
        )
    with pytest.raises(ValueError):
        verify_recovery_expected_head(
            *second,
            successor,
            predecessor=genesis,
            expected_predecessor_sequence=genesis.sequence,
            expected_predecessor_lineage_sha256="f" * 64,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_state", "WRONG"),
        ("predecessor_consistency_verified", False),
        ("automatic_control_allowed", True),
        ("sequence", 2),
        ("checkpoint_sha256", "0" * 64),
        ("lineage_sha256", "0" * 64),
    ],
)
def test_p65_rejects_incompatible_or_drifted_p64_evidence(
    tmp_path: Path, field: str, value: object
) -> None:
    first = _published(tmp_path, "first", "candidate-a", "a")
    genesis = verify_recovery_lineage(*first)
    forged = replace(genesis, **{field: value})
    with pytest.raises(ValueError):
        verify_recovery_expected_head(
            *first,
            forged,
            expected_predecessor_sequence=0,
            expected_predecessor_lineage_sha256=GENESIS_PREDECESSOR_SHA256,
        )


def test_p65_does_not_call_stale_anchor_trusted(tmp_path: Path) -> None:
    first = _published(tmp_path, "first", "candidate-a", "a")
    genesis = verify_recovery_lineage(*first)
    second = _published(tmp_path, "second", "candidate-c", "c")
    successor = verify_recovery_lineage(*second, predecessor=genesis)
    third = verify_recovery_lineage(*first, predecessor=successor)

    # P65 can verify extension of whichever exact predecessor the caller supplies;
    # it does not know whether that externally supplied predecessor is the latest trusted head.
    anchored = verify_recovery_expected_head(
        *first,
        third,
        predecessor=successor,
        expected_predecessor_sequence=successor.sequence,
        expected_predecessor_lineage_sha256=successor.lineage_sha256,
    )
    assert anchored.expected_head_extension_verified is True
    assert "does not prove that the supplied anchor is authentic" in TRUTH_BOUNDARY
