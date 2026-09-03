"""Verify recovery-lineage extension against a minimal caller-supplied head anchor.

P65 narrows the state that an external startup/recovery coordinator must retain from
P64's full predecessor receipt to two values: the predecessor sequence and lineage
SHA-256. The gate recomputes the exact P64 receipt and requires its predecessor link
to match that supplied anchor.

The anchor is supplied by the caller. This module verifies consistency relative to
it; it does not establish that the anchor came from trusted, monotonic, durable, or
independent storage.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from .dataplane import VersionedArtifactRouter
from .dataplane_recovery_generation import RecoveryGenerationEvidence
from .dataplane_recovery_lineage import (
    EVIDENCE_STATE as P64_EVIDENCE_STATE,
    GENESIS_PREDECESSOR_SHA256,
    RecoveryLineageEvidence,
    verify_recovery_lineage,
)
from .dataplane_recovery_store import RecoveryStoreEvidence
from .dataplane_recovery_store_rebootstrap import RecoveryStoreRebootstrapEvidence

EVIDENCE_STATE = "LOCAL_DATA_PLANE_RECOVERY_EXPECTED_HEAD_CONSISTENCY_VERIFIED"
TRUTH_BOUNDARY = (
    "This gate proves only that exact recomputed P64 lineage extends the caller-supplied expected predecessor sequence and "
    "lineage SHA-256 (or the explicit genesis anchor). It does not prove that the supplied anchor is authentic, latest, "
    "monotonic, independently retained, power-loss durable, TPM/HSM-backed, remotely witnessed, or rollback resistant. "
    "It also does not establish distributed consensus, native-object recovery, cross-process hot swap, HA, production "
    "readiness, benchmark performance, or automatic-control authority."
)


def _anchor_sequence(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("expected-head anchor sequence must be a non-negative integer")
    return value


def _sha256(value: object) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError("expected-head anchor SHA-256 must be 64 lowercase hexadecimal characters")
    if value.lower() != value or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError("expected-head anchor SHA-256 must be 64 lowercase hexadecimal characters")
    return value


@dataclass(frozen=True)
class RecoveryExpectedHeadEvidence:
    sequence: int
    lineage_sha256: str
    expected_predecessor_sequence: int
    expected_predecessor_lineage_sha256: str
    exact_p64_recomputation_verified: bool
    expected_head_extension_verified: bool
    p64_evidence_state: str
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def verify_recovery_expected_head(
    path: str | os.PathLike[str],
    recovered_router: VersionedArtifactRouter,
    store_evidence: RecoveryStoreEvidence,
    store_rebootstrap_evidence: RecoveryStoreRebootstrapEvidence,
    generation_evidence: RecoveryGenerationEvidence,
    lineage_evidence: RecoveryLineageEvidence,
    *,
    expected_predecessor_sequence: int,
    expected_predecessor_lineage_sha256: str,
    predecessor: RecoveryLineageEvidence | None = None,
) -> RecoveryExpectedHeadEvidence:
    """Verify exact P64 lineage and its extension of a caller-supplied minimal anchor."""
    anchor_sequence = _anchor_sequence(expected_predecessor_sequence)
    anchor_sha = _sha256(expected_predecessor_lineage_sha256)

    if lineage_evidence.evidence_state != P64_EVIDENCE_STATE:
        raise ValueError("P64 lineage evidence has an incompatible evidence state")
    if not lineage_evidence.predecessor_consistency_verified:
        raise ValueError("P64 lineage evidence is not predecessor-consistency verified")
    if lineage_evidence.automatic_control_allowed:
        raise ValueError("P64 lineage evidence cannot authorize automatic control")

    if predecessor is None:
        required_sequence = 0
        required_sha = GENESIS_PREDECESSOR_SHA256
    else:
        required_sequence = predecessor.sequence
        required_sha = predecessor.lineage_sha256

    if anchor_sequence != required_sequence or anchor_sha != required_sha:
        raise ValueError("caller-supplied expected-head anchor does not match the P64 predecessor")

    recomputed = verify_recovery_lineage(
        path,
        recovered_router,
        store_evidence,
        store_rebootstrap_evidence,
        generation_evidence,
        predecessor=predecessor,
        sequence=lineage_evidence.sequence,
    )
    if recomputed != lineage_evidence:
        raise ValueError("supplied P64 lineage evidence does not match exact recovery recomputation")
    if lineage_evidence.sequence != anchor_sequence + 1:
        raise ValueError("P64 lineage does not extend the expected-head anchor by exactly one")
    if lineage_evidence.predecessor_lineage_sha256 != anchor_sha:
        raise ValueError("P64 predecessor link does not match the expected-head anchor")

    return RecoveryExpectedHeadEvidence(
        sequence=lineage_evidence.sequence,
        lineage_sha256=lineage_evidence.lineage_sha256,
        expected_predecessor_sequence=anchor_sequence,
        expected_predecessor_lineage_sha256=anchor_sha,
        exact_p64_recomputation_verified=True,
        expected_head_extension_verified=True,
        p64_evidence_state=lineage_evidence.evidence_state,
    )
