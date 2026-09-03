"""Bind verified recovery checkpoints into an explicit local lineage.

P64 adds a narrow anti-rollback consistency primitive above P63. Router generations
are intentionally reset on fresh bootstrap and are not durable epochs, so ordering
recovery checkpoints with those generation values would be unsound. Instead, this
gate derives a content-addressed lineage receipt whose sequence is defined only
relative to an explicitly supplied predecessor receipt.

The predecessor remains caller-supplied state. Therefore this gate can detect
rollback/fork inconsistencies relative to a trusted predecessor receipt, but it is
not a trusted monotonic counter, remote transparency log, TPM-backed anchor, or
Byzantine/distributed consensus mechanism.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass

from .dataplane import VersionedArtifactRouter
from .dataplane_recovery_generation import (
    EVIDENCE_STATE as P63_EVIDENCE_STATE,
    RecoveryGenerationEvidence,
    verify_recovery_generation_semantics,
)
from .dataplane_recovery_store import RecoveryStoreEvidence
from .dataplane_recovery_store_rebootstrap import RecoveryStoreRebootstrapEvidence

EVIDENCE_STATE = "LOCAL_DATA_PLANE_RECOVERY_LINEAGE_CONSISTENCY_VERIFIED"
GENESIS_PREDECESSOR_SHA256 = "0" * 64
TRUTH_BOUNDARY = (
    "This gate proves only deterministic checkpoint-lineage consistency relative to the explicitly supplied predecessor "
    "receipt after fresh P63 recomputation. It can fail closed on sequence, predecessor, checkpoint, payload or P63-binding "
    "drift relative to that supplied predecessor. It does not create an externally trusted monotonic counter, immutable "
    "remote log, TPM/HSM-backed rollback protection, distributed consensus, power-loss durability, native-object recovery, "
    "cross-process hot swap, HA, production readiness or performance evidence."
)


def _canonical_sha(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _positive_sequence(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("lineage sequence must be a positive integer")
    return value


@dataclass(frozen=True)
class RecoveryLineageEvidence:
    sequence: int
    checkpoint_sha256: str
    payload_sha256: str
    p63_generation_binding_sha256: str
    predecessor_lineage_sha256: str
    lineage_sha256: str
    predecessor_consistency_verified: bool
    p63_evidence_state: str
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def verify_recovery_lineage(
    path: str | os.PathLike[str],
    recovered_router: VersionedArtifactRouter,
    store_evidence: RecoveryStoreEvidence,
    store_rebootstrap_evidence: RecoveryStoreRebootstrapEvidence,
    generation_evidence: RecoveryGenerationEvidence,
    *,
    predecessor: RecoveryLineageEvidence | None = None,
    sequence: int | None = None,
) -> RecoveryLineageEvidence:
    """Verify exact P63 evidence and bind it to an explicit predecessor receipt."""
    if generation_evidence.evidence_state != P63_EVIDENCE_STATE:
        raise ValueError("P63 generation evidence has an incompatible evidence state")
    if not generation_evidence.source_generation_provenance_verified:
        raise ValueError("P63 generation evidence is not source-provenance verified")
    if not generation_evidence.fresh_bootstrap_generation_verified:
        raise ValueError("P63 generation evidence is not fresh-bootstrap verified")
    if generation_evidence.automatic_control_allowed:
        raise ValueError("P63 generation evidence cannot authorize automatic control")

    recomputed_p63 = verify_recovery_generation_semantics(
        path,
        recovered_router,
        store_evidence,
        store_rebootstrap_evidence,
    )
    if recomputed_p63 != generation_evidence:
        raise ValueError("supplied P63 evidence does not match exact store/router recomputation")

    if predecessor is None:
        expected_sequence = 1
        predecessor_sha = GENESIS_PREDECESSOR_SHA256
    else:
        if predecessor.evidence_state != EVIDENCE_STATE:
            raise ValueError("predecessor lineage evidence has an incompatible evidence state")
        if not predecessor.predecessor_consistency_verified:
            raise ValueError("predecessor lineage evidence is not predecessor-consistency verified")
        if predecessor.automatic_control_allowed:
            raise ValueError("predecessor lineage evidence cannot authorize automatic control")
        predecessor_sequence = _positive_sequence(predecessor.sequence)
        expected_sequence = predecessor_sequence + 1
        predecessor_payload = {
            "sequence": predecessor.sequence,
            "checkpoint_sha256": predecessor.checkpoint_sha256,
            "payload_sha256": predecessor.payload_sha256,
            "p63_generation_binding_sha256": predecessor.p63_generation_binding_sha256,
            "predecessor_lineage_sha256": predecessor.predecessor_lineage_sha256,
            "p63_evidence_state": predecessor.p63_evidence_state,
            "evidence_state": predecessor.evidence_state,
        }
        if _canonical_sha(predecessor_payload) != predecessor.lineage_sha256:
            raise ValueError("predecessor lineage content hash is invalid")
        predecessor_sha = predecessor.lineage_sha256

    if sequence is not None and _positive_sequence(sequence) != expected_sequence:
        raise ValueError("lineage sequence does not extend predecessor by exactly one")

    lineage_payload = {
        "sequence": expected_sequence,
        "checkpoint_sha256": generation_evidence.checkpoint_sha256,
        "payload_sha256": generation_evidence.payload_sha256,
        "p63_generation_binding_sha256": generation_evidence.generation_binding_sha256,
        "predecessor_lineage_sha256": predecessor_sha,
        "p63_evidence_state": generation_evidence.evidence_state,
        "evidence_state": EVIDENCE_STATE,
    }
    return RecoveryLineageEvidence(
        sequence=expected_sequence,
        checkpoint_sha256=generation_evidence.checkpoint_sha256,
        payload_sha256=generation_evidence.payload_sha256,
        p63_generation_binding_sha256=generation_evidence.generation_binding_sha256,
        predecessor_lineage_sha256=predecessor_sha,
        lineage_sha256=_canonical_sha(lineage_payload),
        predecessor_consistency_verified=True,
        p63_evidence_state=generation_evidence.evidence_state,
    )
