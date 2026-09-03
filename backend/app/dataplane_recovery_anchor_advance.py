"""Advance a P66 local expected-head anchor after exact P67 recovery verification.

P68 closes one narrow local startup/recovery seam after P67: once P67 has verified
that the currently stored P66 head identifies the supplied predecessor and that the
current recovery is its exact P65-verified successor, this gate can replace that same
anchor file with the newly verified current head. Immediately before publication it
re-reads the predecessor bytes and requires their exact size/SHA-256/semantic identity
to still match both the supplied P66 and P67 evidence. The new canonical bytes are
then published by same-directory temporary-file replacement and revalidated from the
actual readback bytes.

This is deliberately not a concurrency-safe compare-and-swap primitive. Another
writer can race between the pre-publication read and os.replace because no portable
cross-process lock or filesystem CAS is established here. It also does not make a
local file a trusted monotonic/latest anchor or prevent coordinated rollback.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from .dataplane_recovery_anchor_rebootstrap import (
    EVIDENCE_STATE as P67_EVIDENCE_STATE,
    RecoveryStoredExpectedHeadEvidence,
)
from .dataplane_recovery_anchor_store import (
    EVIDENCE_STATE as P66_EVIDENCE_STATE,
    RecoveryExpectedHeadStoreEvidence,
    load_recovery_expected_head,
)

EVIDENCE_STATE = "LOCAL_DATA_PLANE_RECOVERY_EXPECTED_HEAD_ADVANCEMENT_CONSISTENCY_VERIFIED"
TRUTH_BOUNDARY = (
    "This gate proves only that, immediately before one local publication attempt, the exact bytes read from the caller-"
    "selected P66 anchor path still matched the supplied P66 predecessor publication evidence and the predecessor identity "
    "bound by compatible P67 evidence; it then published the P67-verified current head as strict canonical JSON using a same-"
    "directory temporary file, file fsync, atomic replacement, and exact readback verification. It is not a concurrency-safe "
    "filesystem compare-and-swap: another writer may race between the pre-publication read and replacement because this gate "
    "establishes no portable cross-process lock or atomic conditional-write primitive. It also does not prove that either head "
    "is externally authentic, globally latest, independently monotonic, power-loss durable, TPM/HSM-backed, remotely witnessed, "
    "or rollback resistant, and establishes no distributed consensus, HA, native-object recovery, cross-process hot swap, "
    "production readiness, benchmark performance, or automatic-control authority."
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _positive_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _sha(value: object, *, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{field} must be 64 lowercase hexadecimal characters")
    if value.lower() != value or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{field} must be 64 lowercase hexadecimal characters")
    return value


def _canonical_payload(sequence: int, lineage_sha256: str) -> bytes:
    return json.dumps(
        {"lineage_sha256": lineage_sha256, "sequence": sequence},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


@dataclass(frozen=True)
class RecoveryExpectedHeadAdvanceEvidence:
    predecessor_sequence: int
    predecessor_lineage_sha256: str
    predecessor_payload_sha256: str
    predecessor_payload_size_bytes: int
    sequence: int
    lineage_sha256: str
    anchor_payload_sha256: str
    anchor_payload_size_bytes: int
    predecessor_identity_rechecked: bool
    exact_p67_successor_bound: bool
    canonical_anchor_verified: bool
    same_directory_replace_used: bool
    readback_identity_verified: bool
    advancement_consistency_verified: bool
    p66_evidence_state: str
    p67_evidence_state: str
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def advance_recovery_expected_head(
    path: str | os.PathLike[str],
    predecessor_store_evidence: RecoveryExpectedHeadStoreEvidence,
    recovery_evidence: RecoveryStoredExpectedHeadEvidence,
) -> RecoveryExpectedHeadAdvanceEvidence:
    """Replace the exact P66 predecessor anchor with the exact P67-verified current head."""
    if predecessor_store_evidence.evidence_state != P66_EVIDENCE_STATE:
        raise ValueError("P66 predecessor anchor-store evidence has an incompatible evidence state")
    if not predecessor_store_evidence.canonical_anchor_verified:
        raise ValueError("P66 predecessor anchor-store evidence is not canonical-anchor verified")
    if not predecessor_store_evidence.same_directory_replace_used:
        raise ValueError("P66 predecessor anchor-store evidence does not record same-directory replacement")
    if not predecessor_store_evidence.readback_identity_verified or not predecessor_store_evidence.store_consistency_verified:
        raise ValueError("P66 predecessor anchor-store evidence is not store-consistency verified")
    if predecessor_store_evidence.automatic_control_allowed:
        raise ValueError("P66 predecessor anchor-store evidence cannot authorize automatic control")

    if recovery_evidence.evidence_state != P67_EVIDENCE_STATE:
        raise ValueError("P67 stored-head recovery evidence has an incompatible evidence state")
    if not recovery_evidence.stored_anchor_identity_verified:
        raise ValueError("P67 evidence is not stored-anchor identity verified")
    if not recovery_evidence.predecessor_anchor_match_verified:
        raise ValueError("P67 evidence is not predecessor-anchor match verified")
    if not recovery_evidence.exact_p65_recomputation_verified:
        raise ValueError("P67 evidence is not exact-P65 recomputation verified")
    if not recovery_evidence.stored_head_recovery_consistency_verified:
        raise ValueError("P67 evidence is not stored-head recovery consistency verified")
    if recovery_evidence.automatic_control_allowed:
        raise ValueError("P67 evidence cannot authorize automatic control")

    predecessor_sequence = _positive_int(predecessor_store_evidence.sequence, field="P66 predecessor sequence")
    predecessor_lineage = _sha(predecessor_store_evidence.lineage_sha256, field="P66 predecessor lineage SHA-256")
    predecessor_payload_sha = _sha(
        predecessor_store_evidence.anchor_payload_sha256, field="P66 predecessor payload SHA-256"
    )
    predecessor_payload_size = _positive_int(
        predecessor_store_evidence.anchor_payload_size_bytes, field="P66 predecessor payload size"
    )
    current_sequence = _positive_int(recovery_evidence.sequence, field="P67 current sequence")
    current_lineage = _sha(recovery_evidence.lineage_sha256, field="P67 current lineage SHA-256")

    if recovery_evidence.predecessor_sequence != predecessor_sequence:
        raise ValueError("P67 predecessor sequence does not match P66 predecessor evidence")
    if recovery_evidence.predecessor_lineage_sha256 != predecessor_lineage:
        raise ValueError("P67 predecessor lineage does not match P66 predecessor evidence")
    if recovery_evidence.anchor_payload_sha256 != predecessor_payload_sha:
        raise ValueError("P67 predecessor payload SHA-256 does not match P66 predecessor evidence")
    if recovery_evidence.anchor_payload_size_bytes != predecessor_payload_size:
        raise ValueError("P67 predecessor payload size does not match P66 predecessor evidence")
    if current_sequence != predecessor_sequence + 1:
        raise ValueError("P67 current head must extend the P66 predecessor by exactly one sequence")

    target = Path(path)
    if not target.name:
        raise ValueError("recovery expected-head store path must name a file")

    # Recheck the exact predecessor bytes immediately before constructing/publicizing
    # the successor. This narrows stale-evidence windows but is explicitly not a CAS.
    predecessor_bytes = target.read_bytes()
    if len(predecessor_bytes) != predecessor_payload_size:
        raise ValueError("stored predecessor payload-size drift before advancement")
    if _sha256(predecessor_bytes) != predecessor_payload_sha:
        raise ValueError("stored predecessor payload SHA-256 drift before advancement")
    stored_predecessor = load_recovery_expected_head(path, expected_payload_sha256=predecessor_payload_sha)
    if stored_predecessor.sequence != predecessor_sequence or stored_predecessor.lineage_sha256 != predecessor_lineage:
        raise ValueError("stored predecessor semantic identity drift before advancement")

    payload = _canonical_payload(current_sequence, current_lineage)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.morpheus-head-advance-tmp-{os.getpid()}")
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()

    readback = target.read_bytes()
    if readback != payload:
        raise ValueError("advanced recovery expected-head readback differs from published payload")
    advanced = load_recovery_expected_head(path, expected_payload_sha256=_sha256(payload))
    if advanced.sequence != current_sequence or advanced.lineage_sha256 != current_lineage:
        raise ValueError("advanced recovery expected-head readback identity drift")

    return RecoveryExpectedHeadAdvanceEvidence(
        predecessor_sequence=predecessor_sequence,
        predecessor_lineage_sha256=predecessor_lineage,
        predecessor_payload_sha256=predecessor_payload_sha,
        predecessor_payload_size_bytes=predecessor_payload_size,
        sequence=current_sequence,
        lineage_sha256=current_lineage,
        anchor_payload_sha256=_sha256(readback),
        anchor_payload_size_bytes=len(readback),
        predecessor_identity_rechecked=True,
        exact_p67_successor_bound=True,
        canonical_anchor_verified=True,
        same_directory_replace_used=True,
        readback_identity_verified=True,
        advancement_consistency_verified=True,
        p66_evidence_state=predecessor_store_evidence.evidence_state,
        p67_evidence_state=recovery_evidence.evidence_state,
    )
