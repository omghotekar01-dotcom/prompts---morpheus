"""Local canonical persistence for the minimal P65 recovery expected-head anchor.

P66 closes one narrow startup/recovery seam after P65: once a P65 verification has
produced the current recovery lineage head, a caller may persist exactly the two
values needed as the expected predecessor for a later recovery attempt: ``sequence``
and ``lineage_sha256``. The on-disk representation is strict canonical JSON and is
validated again from the bytes actually read back after publication.

This is deliberately a local integrity/continuity primitive, not a trusted monotonic
anchor. A party able to roll back or replace this file can present an older internally
valid head. Strong rollback resistance still requires a separately protected latest-
head source (for example an independently administered monotonic/attested service).
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from .dataplane_recovery_anchor import (
    EVIDENCE_STATE as P65_EVIDENCE_STATE,
    RecoveryExpectedHeadEvidence,
)

EVIDENCE_STATE = "LOCAL_DATA_PLANE_RECOVERY_EXPECTED_HEAD_STORE_CONSISTENCY_VERIFIED"
TRUTH_BOUNDARY = (
    "This gate proves only that the minimal current head derived from compatible supplied P65 evidence was serialized as "
    "strict canonical JSON, published to one caller-selected local filesystem path using same-directory temporary-file "
    "replacement, and revalidated from exact readback bytes with matching SHA-256 identity. It does not independently "
    "recompute P65, prove that the P65 evidence is externally authentic, or make the local file a trusted/latest/monotonic "
    "anchor. A rollback or coordinated replacement of this file can still present an older internally valid head. It also "
    "does not establish power-loss durability, TPM/HSM protection, remote witnessing, distributed consensus, HA, native-"
    "object recovery, cross-process hot swap, production readiness, benchmark performance, or automatic-control authority."
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sequence(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("stored recovery head sequence must be a positive integer")
    return value


def _lineage_sha256(value: object) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError("stored recovery head lineage SHA-256 must be 64 lowercase hexadecimal characters")
    if value.lower() != value or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError("stored recovery head lineage SHA-256 must be 64 lowercase hexadecimal characters")
    return value


def _canonical_payload(sequence: int, lineage_sha256: str) -> bytes:
    return json.dumps(
        {"lineage_sha256": lineage_sha256, "sequence": sequence},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


@dataclass(frozen=True)
class RecoveryStoredHead:
    sequence: int
    lineage_sha256: str

    def as_dict(self) -> dict[str, object]:
        return {"sequence": self.sequence, "lineage_sha256": self.lineage_sha256}


@dataclass(frozen=True)
class RecoveryExpectedHeadStoreEvidence:
    sequence: int
    lineage_sha256: str
    anchor_payload_sha256: str
    anchor_payload_size_bytes: int
    canonical_anchor_verified: bool
    same_directory_replace_used: bool
    readback_identity_verified: bool
    store_consistency_verified: bool
    p65_evidence_state: str
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def _head_from_p65(evidence: RecoveryExpectedHeadEvidence) -> RecoveryStoredHead:
    if evidence.evidence_state != P65_EVIDENCE_STATE:
        raise ValueError("P65 expected-head evidence has an incompatible evidence state")
    if not evidence.exact_p64_recomputation_verified or not evidence.expected_head_extension_verified:
        raise ValueError("P65 expected-head evidence is not fully consistency verified")
    if evidence.automatic_control_allowed:
        raise ValueError("P65 expected-head evidence cannot authorize automatic control")
    return RecoveryStoredHead(
        sequence=_sequence(evidence.sequence),
        lineage_sha256=_lineage_sha256(evidence.lineage_sha256),
    )


def _parse_canonical_payload(payload: bytes) -> RecoveryStoredHead:
    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("stored recovery head must be UTF-8 JSON") from exc
    try:
        raw = json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise ValueError("stored recovery head must be valid JSON") from exc
    if not isinstance(raw, dict) or set(raw) != {"sequence", "lineage_sha256"}:
        raise ValueError("stored recovery head must contain exactly sequence and lineage_sha256")
    head = RecoveryStoredHead(
        sequence=_sequence(raw["sequence"]),
        lineage_sha256=_lineage_sha256(raw["lineage_sha256"]),
    )
    if payload != _canonical_payload(head.sequence, head.lineage_sha256):
        raise ValueError("stored recovery head is not in canonical JSON form")
    return head


def publish_recovery_expected_head(
    path: str | os.PathLike[str], evidence: RecoveryExpectedHeadEvidence
) -> RecoveryExpectedHeadStoreEvidence:
    """Publish the minimal current P65 head and verify the exact local readback bytes."""
    head = _head_from_p65(evidence)
    payload = _canonical_payload(head.sequence, head.lineage_sha256)
    target = Path(path)
    if not target.name:
        raise ValueError("recovery expected-head store path must name a file")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.morpheus-head-tmp-{os.getpid()}")
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
        raise ValueError("recovery expected-head store readback differs from published payload")
    parsed = _parse_canonical_payload(readback)
    if parsed != head:
        raise ValueError("recovery expected-head store readback identity drift")

    return RecoveryExpectedHeadStoreEvidence(
        sequence=head.sequence,
        lineage_sha256=head.lineage_sha256,
        anchor_payload_sha256=_sha256(readback),
        anchor_payload_size_bytes=len(readback),
        canonical_anchor_verified=True,
        same_directory_replace_used=True,
        readback_identity_verified=True,
        store_consistency_verified=True,
        p65_evidence_state=evidence.evidence_state,
    )


def load_recovery_expected_head(
    path: str | os.PathLike[str], *, expected_payload_sha256: str | None = None
) -> RecoveryStoredHead:
    """Load and strictly validate one canonical local recovery expected-head payload."""
    payload = Path(path).read_bytes()
    head = _parse_canonical_payload(payload)
    actual_sha = _sha256(payload)
    if expected_payload_sha256 is not None:
        expected = expected_payload_sha256.strip().casefold()
        if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
            raise ValueError("expected_payload_sha256 must be a 64-character hexadecimal digest")
        if actual_sha != expected:
            raise ValueError("stored recovery head payload SHA-256 does not match expected identity")
    return head
