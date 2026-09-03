"""Bind a P66 local expected-head anchor to exact P65 recovery verification.

P67 closes one narrow startup/recovery seam after P66: the bytes actually present at
the caller-selected P66 anchor path must still match the supplied P66 publication
evidence, that stored head must identify the supplied full P64 predecessor receipt,
and the current recovery must then pass exact P65 recomputation as a one-step
extension of that predecessor.

This is an integrity-composition gate. It does not make either local file trusted or
monotonic and cannot detect a coordinated rollback/replacement of recovery data,
predecessor evidence, and anchor state that remains internally self-consistent.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from .dataplane import VersionedArtifactRouter
from .dataplane_recovery_anchor import (
    EVIDENCE_STATE as P65_EVIDENCE_STATE,
    verify_recovery_expected_head,
)
from .dataplane_recovery_anchor_store import (
    EVIDENCE_STATE as P66_EVIDENCE_STATE,
    RecoveryExpectedHeadStoreEvidence,
    load_recovery_expected_head,
)
from .dataplane_recovery_generation import RecoveryGenerationEvidence
from .dataplane_recovery_lineage import (
    EVIDENCE_STATE as P64_EVIDENCE_STATE,
    RecoveryLineageEvidence,
)
from .dataplane_recovery_store import RecoveryStoreEvidence
from .dataplane_recovery_store_rebootstrap import RecoveryStoreRebootstrapEvidence

EVIDENCE_STATE = "LOCAL_DATA_PLANE_STORED_EXPECTED_HEAD_RECOVERY_CONSISTENCY_VERIFIED"
TRUTH_BOUNDARY = (
    "This gate proves only that exact canonical bytes currently read from one caller-selected P66 local anchor path match "
    "the supplied P66 publication evidence, identify the supplied full P64 predecessor receipt, and that the current recovery "
    "passes exact P65 recomputation as a one-step extension of that stored predecessor head. It does not prove that the local "
    "anchor or predecessor is authentic, latest, monotonic, independently retained, power-loss durable, TPM/HSM-backed, or "
    "remotely witnessed. A coordinated rollback or replacement of recovery data, predecessor evidence, and local anchor state "
    "can remain internally consistent and is not prevented by this gate. It also does not establish distributed consensus, HA, "
    "native-object recovery, cross-process hot swap, production readiness, benchmark performance, or automatic-control authority."
)


def _canonical_sha(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _positive_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _sha256(value: object, *, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{field} must be 64 lowercase hexadecimal characters")
    if value.lower() != value or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{field} must be 64 lowercase hexadecimal characters")
    return value


@dataclass(frozen=True)
class RecoveryStoredExpectedHeadEvidence:
    sequence: int
    lineage_sha256: str
    predecessor_sequence: int
    predecessor_lineage_sha256: str
    anchor_payload_sha256: str
    anchor_payload_size_bytes: int
    binding_sha256: str
    stored_anchor_identity_verified: bool
    predecessor_anchor_match_verified: bool
    exact_p65_recomputation_verified: bool
    stored_head_recovery_consistency_verified: bool
    p66_evidence_state: str
    p65_evidence_state: str
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def verify_recovery_against_stored_expected_head(
    recovery_path: str | os.PathLike[str],
    anchor_path: str | os.PathLike[str],
    recovered_router: VersionedArtifactRouter,
    store_evidence: RecoveryStoreEvidence,
    store_rebootstrap_evidence: RecoveryStoreRebootstrapEvidence,
    generation_evidence: RecoveryGenerationEvidence,
    lineage_evidence: RecoveryLineageEvidence,
    predecessor: RecoveryLineageEvidence,
    anchor_store_evidence: RecoveryExpectedHeadStoreEvidence,
) -> RecoveryStoredExpectedHeadEvidence:
    """Verify a current recovery as the exact successor of the head stored by P66."""
    if anchor_store_evidence.evidence_state != P66_EVIDENCE_STATE:
        raise ValueError("P66 anchor-store evidence has an incompatible evidence state")
    if not anchor_store_evidence.canonical_anchor_verified:
        raise ValueError("P66 anchor-store evidence is not canonical-anchor verified")
    if not anchor_store_evidence.same_directory_replace_used:
        raise ValueError("P66 anchor-store evidence does not record same-directory replacement")
    if (
        not anchor_store_evidence.readback_identity_verified
        or not anchor_store_evidence.store_consistency_verified
    ):
        raise ValueError("P66 anchor-store evidence is not store-consistency verified")
    if anchor_store_evidence.p65_evidence_state != P65_EVIDENCE_STATE:
        raise ValueError("P66 anchor-store evidence does not derive from compatible P65 evidence")
    if anchor_store_evidence.automatic_control_allowed:
        raise ValueError("P66 anchor-store evidence cannot authorize automatic control")

    evidence_sequence = _positive_int(anchor_store_evidence.sequence, field="P66 stored-head sequence")
    evidence_lineage_sha = _sha256(
        anchor_store_evidence.lineage_sha256, field="P66 stored-head lineage SHA-256"
    )
    evidence_payload_sha = _sha256(
        anchor_store_evidence.anchor_payload_sha256, field="P66 anchor payload SHA-256"
    )
    evidence_payload_size = _positive_int(
        anchor_store_evidence.anchor_payload_size_bytes, field="P66 anchor payload size"
    )

    anchor_payload = Path(anchor_path).read_bytes()
    if len(anchor_payload) != evidence_payload_size:
        raise ValueError("P66 anchor-store evidence payload-size drift")
    stored_head = load_recovery_expected_head(
        anchor_path, expected_payload_sha256=evidence_payload_sha
    )
    if stored_head.sequence != evidence_sequence or stored_head.lineage_sha256 != evidence_lineage_sha:
        raise ValueError("P66 anchor-store evidence does not match exact stored head identity")

    if predecessor.evidence_state != P64_EVIDENCE_STATE:
        raise ValueError("P64 predecessor evidence has an incompatible evidence state")
    if not predecessor.predecessor_consistency_verified:
        raise ValueError("P64 predecessor evidence is not predecessor-consistency verified")
    if predecessor.automatic_control_allowed:
        raise ValueError("P64 predecessor evidence cannot authorize automatic control")
    if predecessor.sequence != stored_head.sequence or predecessor.lineage_sha256 != stored_head.lineage_sha256:
        raise ValueError("stored P66 head does not identify the supplied P64 predecessor")

    p65 = verify_recovery_expected_head(
        recovery_path,
        recovered_router,
        store_evidence,
        store_rebootstrap_evidence,
        generation_evidence,
        lineage_evidence,
        expected_predecessor_sequence=stored_head.sequence,
        expected_predecessor_lineage_sha256=stored_head.lineage_sha256,
        predecessor=predecessor,
    )
    if p65.evidence_state != P65_EVIDENCE_STATE:
        raise ValueError("P65 recovery evidence has an incompatible evidence state")
    if not p65.exact_p64_recomputation_verified or not p65.expected_head_extension_verified:
        raise ValueError("P65 recovery evidence is not fully consistency verified")
    if p65.automatic_control_allowed:
        raise ValueError("P65 recovery evidence cannot authorize automatic control")

    binding_payload = {
        "sequence": p65.sequence,
        "lineage_sha256": p65.lineage_sha256,
        "predecessor_sequence": stored_head.sequence,
        "predecessor_lineage_sha256": stored_head.lineage_sha256,
        "anchor_payload_sha256": evidence_payload_sha,
        "anchor_payload_size_bytes": evidence_payload_size,
        "p66_evidence_state": anchor_store_evidence.evidence_state,
        "p65_evidence_state": p65.evidence_state,
    }
    return RecoveryStoredExpectedHeadEvidence(
        sequence=p65.sequence,
        lineage_sha256=p65.lineage_sha256,
        predecessor_sequence=stored_head.sequence,
        predecessor_lineage_sha256=stored_head.lineage_sha256,
        anchor_payload_sha256=evidence_payload_sha,
        anchor_payload_size_bytes=evidence_payload_size,
        binding_sha256=_canonical_sha(binding_payload),
        stored_anchor_identity_verified=True,
        predecessor_anchor_match_verified=True,
        exact_p65_recomputation_verified=True,
        stored_head_recovery_consistency_verified=True,
        p66_evidence_state=anchor_store_evidence.evidence_state,
        p65_evidence_state=p65.evidence_state,
    )
