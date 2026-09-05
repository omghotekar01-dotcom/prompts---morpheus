"""Persist the minimum verified P110 canonical P109-replay identity locally.

P111 closes only the local-retention seam left explicit by P110. A caller supplies
verified P110 replay evidence; this gate validates that evidence contract, reduces
it to a strict canonical identity for later independent replay, writes through a
same-directory temporary file, fsyncs it, atomically replaces the selected
destination, and verifies exact stored bytes.

The resulting file is local historical evidence, not an authenticated,
freshness-bearing, monotonic, or startup-authoritative trust root.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .recovery_p110 import (
    EVIDENCE_STATE as P110_EVIDENCE_STATE,
    RecoveryP109ReplayEvidence,
    _FIELDS as P110_RECEIPT_FIELDS,
)

EVIDENCE_STATE = P110_EVIDENCE_STATE + "_IDENTITY_STORED"
TRUTH_BOUNDARY = (
    "This gate proves only that compatible verified P110 replay evidence was reduced to a strict canonical local identity record, "
    "written through a same-directory temporary file, fsynced, atomically replaced at the selected path, and read back with exact "
    "byte identity during this call. The file is local historical evidence, not an authenticated, freshness-bearing, or independently "
    "monotonic trust anchor. This gate does not authenticate P110 evidence or the filesystem, prove freshness/latest/global/monotonic "
    "head truth, prevent rollback/replay or coordinated replacement, rerun P109/P110 or dependencies, authorize startup or mutation, "
    "provide universal crash or power-loss durability, CAS, leases, fencing, TPM/HSM protection, remote witnessing, distributed consensus, "
    "HA, native-object recovery, cross-process hot swap, production readiness, benchmark evidence, novelty evidence, or automatic-control authority."
)

_FIELDS = (
    *P110_RECEIPT_FIELDS,
    ("p109_receipt_payload_sha256", "sha"),
    ("p109_receipt_payload_size_bytes", "int"),
)
_REQUIRED_VERIFICATION_FLAGS = (
    "expected_payload_identity_verified",
    "canonical_receipt_verified",
    "dependency_state_verified",
    "p105_p107_composition_binding_recomputed_verified",
)


def _positive_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _sha256(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value.lower() != value
        or any(ch not in "0123456789abcdef" for ch in value)
    ):
        raise ValueError(f"{field} must be 64 lowercase hexadecimal characters")
    return value


def _canonical(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


@dataclass(frozen=True)
class RecoveryP110ReplayIdentityStoreEvidence:
    sequence: int
    lineage_sha256: str
    binding_receipt_payload_sha256: str
    binding_receipt_payload_size_bytes: int
    receipt_identity_binding_sha256: str
    retained_identity_payload_sha256: str
    retained_identity_payload_size_bytes: int
    replay_stored_identity_binding_sha256: str
    replay_binding_receipt_payload_sha256: str
    replay_binding_receipt_payload_size_bytes: int
    retained_replay_identity_payload_sha256: str
    retained_replay_identity_payload_size_bytes: int
    replay_retained_identity_binding_sha256: str
    replay_retained_identity_binding_receipt_payload_sha256: str
    replay_retained_identity_binding_receipt_payload_size_bytes: int
    retained_replay_receipt_identity_payload_sha256: str
    retained_replay_receipt_identity_payload_size_bytes: int
    replay_retained_receipt_identity_binding_sha256: str
    replay_retained_receipt_identity_binding_receipt_payload_sha256: str
    replay_retained_receipt_identity_binding_receipt_payload_size_bytes: int
    retained_replayed_receipt_identity_payload_sha256: str
    retained_replayed_receipt_identity_payload_size_bytes: int
    replayed_receipt_retained_identity_binding_sha256: str
    replayed_receipt_retained_identity_binding_receipt_payload_sha256: str
    replayed_receipt_retained_identity_binding_receipt_payload_size_bytes: int
    retained_p101_record_payload_sha256: str
    retained_p101_record_payload_size_bytes: int
    p100_p102_composition_binding_sha256: str
    p104_receipt_payload_sha256: str
    p104_receipt_payload_size_bytes: int
    retained_p106_record_payload_sha256: str
    retained_p106_record_payload_size_bytes: int
    p105_p107_composition_binding_sha256: str
    p109_receipt_payload_sha256: str
    p109_receipt_payload_size_bytes: int
    stored_payload_sha256: str
    stored_payload_size_bytes: int
    destination_path: str
    p110_evidence_state_verified: bool
    p110_verification_flags_verified: bool
    exact_readback_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def store_p110_replay_identity(
    evidence: RecoveryP109ReplayEvidence,
    *,
    destination_path: str | os.PathLike[str],
) -> RecoveryP110ReplayIdentityStoreEvidence:
    """Persist the minimal canonical identity of one compatible P110 replay."""
    if not isinstance(evidence, RecoveryP109ReplayEvidence):
        raise ValueError("P110 replay evidence has an incompatible type")
    if evidence.evidence_state != P110_EVIDENCE_STATE:
        raise ValueError("P110 replay evidence state is incompatible")
    if evidence.automatic_control_allowed is not False:
        raise ValueError("P110 replay evidence must not grant automatic-control authority")
    if any(getattr(evidence, flag, None) is not True for flag in _REQUIRED_VERIFICATION_FLAGS):
        raise ValueError("P110 replay evidence verification flags are incomplete")

    values: dict[str, object] = {}
    for field, kind in _FIELDS:
        raw = getattr(evidence, field, None)
        values[field] = (
            _positive_int(raw, field=f"P110 {field}")
            if kind == "int"
            else _sha256(raw, field=f"P110 {field}")
        )

    payload = {**values, "p110_evidence_state": P110_EVIDENCE_STATE}
    encoded = _canonical(payload)
    encoded_sha = hashlib.sha256(encoded).hexdigest()

    destination = Path(destination_path)
    if not destination.name:
        raise ValueError("destination path must identify a file")
    destination.parent.mkdir(parents=True, exist_ok=True)

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        finally:
            raise

    stored = destination.read_bytes()
    if stored != encoded:
        raise ValueError("stored P110 replay identity differs from published bytes")
    if hashlib.sha256(stored).hexdigest() != encoded_sha:
        raise ValueError("stored P110 replay identity SHA-256 mismatch")

    return RecoveryP110ReplayIdentityStoreEvidence(
        **values,
        stored_payload_sha256=encoded_sha,
        stored_payload_size_bytes=len(encoded),
        destination_path=str(destination),
        p110_evidence_state_verified=True,
        p110_verification_flags_verified=True,
        exact_readback_verified=True,
    )
