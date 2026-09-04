"""Persist the minimum P75 startup-admission receipt identity locally.

P76 closes the local-retention seam left explicit by P75. A caller supplies
verified P75 replay evidence; this gate validates that evidence contract, writes
only the minimum receipt identity needed for a later consumer, fsyncs and
atomically replaces the destination, then verifies exact stored bytes.

The store is deliberately local evidence, not a trust root. Local persistence
does not authenticate the receipt identity, prove freshness, prevent rollback,
or authorize startup or mutation.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .dataplane_recovery_startup_receipt_replay import (
    EVIDENCE_STATE as P75_EVIDENCE_STATE,
    RecoveryStartupAdmissionReceiptReplayEvidence,
)

EVIDENCE_STATE = "LOCAL_DATA_PLANE_RECOVERY_STARTUP_ADMISSION_RECEIPT_IDENTITY_STORED"
TRUTH_BOUNDARY = (
    "This gate proves only that compatible verified P75 evidence was reduced to a strict canonical local identity record, written "
    "through a same-directory temporary file, fsynced, atomically replaced at the selected path, and read back with exact byte "
    "identity during this call. The file is not an authenticated or independently monotonic trust anchor. This gate does not prove "
    "freshness or latest/global head truth, prevent rollback/replay or coordinated replacement, rerun P67-P75, authorize startup "
    "or mutation, provide universal power-loss durability, CAS, leases, fencing, TPM/HSM protection, remote witnessing, distributed "
    "consensus, HA, native-object recovery, cross-process hot swap, production readiness, benchmark evidence, novelty evidence, or "
    "automatic-control authority."
)

_REQUIRED_VERIFICATION_FLAGS = (
    "expected_payload_identity_verified",
    "canonical_receipt_verified",
    "admission_binding_recomputed_verified",
    "dependency_states_verified",
)


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


def _canonical(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


@dataclass(frozen=True)
class RecoveryStartupReceiptIdentityStoreEvidence:
    sequence: int
    lineage_sha256: str
    receipt_payload_sha256: str
    receipt_payload_size_bytes: int
    admission_binding_sha256: str
    stored_payload_sha256: str
    stored_payload_size_bytes: int
    destination_path: str
    p75_evidence_state_verified: bool
    p75_verification_flags_verified: bool
    exact_readback_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def store_recovery_startup_receipt_identity(
    evidence: RecoveryStartupAdmissionReceiptReplayEvidence,
    *,
    destination_path: str | os.PathLike[str],
) -> RecoveryStartupReceiptIdentityStoreEvidence:
    """Persist the minimal canonical identity of one compatible P75 receipt."""
    if not isinstance(evidence, RecoveryStartupAdmissionReceiptReplayEvidence):
        raise ValueError("P75 replay evidence has an incompatible type")
    if evidence.evidence_state != P75_EVIDENCE_STATE:
        raise ValueError("P75 replay evidence state is incompatible")
    if evidence.automatic_control_allowed is not False:
        raise ValueError("P75 replay evidence must not grant automatic-control authority")
    if any(getattr(evidence, flag, None) is not True for flag in _REQUIRED_VERIFICATION_FLAGS):
        raise ValueError("P75 replay evidence verification flags are incomplete")

    sequence = _positive_int(evidence.sequence, field="P75 sequence")
    lineage = _sha256(evidence.lineage_sha256, field="P75 lineage SHA-256")
    receipt_sha = _sha256(
        evidence.receipt_payload_sha256, field="P75 receipt payload SHA-256"
    )
    receipt_size = _positive_int(
        evidence.receipt_payload_size_bytes, field="P75 receipt payload size"
    )
    admission_binding = _sha256(
        evidence.admission_binding_sha256, field="P75 admission binding SHA-256"
    )

    payload = {
        "admission_binding_sha256": admission_binding,
        "lineage_sha256": lineage,
        "p75_evidence_state": P75_EVIDENCE_STATE,
        "receipt_payload_sha256": receipt_sha,
        "receipt_payload_size_bytes": receipt_size,
        "sequence": sequence,
    }
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
        raise ValueError("stored startup-admission receipt identity differs from published bytes")
    if hashlib.sha256(stored).hexdigest() != encoded_sha:
        raise ValueError("stored startup-admission receipt identity SHA-256 mismatch")

    return RecoveryStartupReceiptIdentityStoreEvidence(
        sequence=sequence,
        lineage_sha256=lineage,
        receipt_payload_sha256=receipt_sha,
        receipt_payload_size_bytes=receipt_size,
        admission_binding_sha256=admission_binding,
        stored_payload_sha256=encoded_sha,
        stored_payload_size_bytes=len(encoded),
        destination_path=str(destination),
        p75_evidence_state_verified=True,
        p75_verification_flags_verified=True,
        exact_readback_verified=True,
    )
