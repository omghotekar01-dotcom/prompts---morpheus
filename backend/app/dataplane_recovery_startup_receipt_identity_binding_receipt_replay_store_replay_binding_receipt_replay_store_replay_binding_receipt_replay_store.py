"""Persist the minimum verified P90 replay/retained-identity receipt identity locally.

P91 closes only the local-retention seam left explicit by P90. A caller supplies
verified P90 replay evidence; this gate validates that evidence contract, reduces
it to the minimum canonical identity required by a later independent replay
consumer, writes through a same-directory temporary file, fsyncs it, atomically
replaces the selected destination, and verifies exact stored bytes.

The resulting file is local historical evidence, not an authenticated,
freshness-bearing, or monotonic trust root. Persistence does not authorize
startup or mutation.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay import (
    EVIDENCE_STATE as P90_EVIDENCE_STATE,
    RecoveryStartupReplayRetainedIdentityBindingReceiptReplayEvidence,
)

EVIDENCE_STATE = (
    "LOCAL_DATA_PLANE_RECOVERY_STARTUP_ADMISSION_STORED_RECEIPT_BINDING_RECEIPT_REPLAY_STORED_IDENTITY_BINDING_"
    "RECEIPT_REPLAY_IDENTITY_STORED_REPLAY_BINDING_RECEIPT_REPLAY_VERIFIED_IDENTITY_STORED"
)
TRUTH_BOUNDARY = (
    "This gate proves only that compatible verified P90 replay evidence was reduced to a strict canonical local identity record, "
    "written through a same-directory temporary file, fsynced, atomically replaced at the selected path, and read back with exact "
    "byte identity during this call. The file is local historical evidence, not an authenticated, freshness-bearing, or independently "
    "monotonic trust anchor. This gate does not authenticate P90 evidence or the filesystem, prove freshness/latest/global/monotonic "
    "head truth, prevent rollback/replay or coordinated replacement, rerun P89/P90 or their dependencies, authorize startup or mutation, "
    "provide universal crash or power-loss durability, CAS, leases, fencing, TPM/HSM protection, remote witnessing, distributed consensus, "
    "HA, native-object recovery, cross-process hot swap, production readiness, benchmark evidence, novelty evidence, or automatic-control authority."
)

_REQUIRED_VERIFICATION_FLAGS = (
    "expected_payload_identity_verified",
    "canonical_receipt_verified",
    "dependency_state_verified",
    "replay_retained_identity_binding_recomputed_verified",
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
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


@dataclass(frozen=True)
class RecoveryStartupReplayRetainedIdentityBindingReceiptReplayIdentityStoreEvidence:
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
    stored_payload_sha256: str
    stored_payload_size_bytes: int
    destination_path: str
    p90_evidence_state_verified: bool
    p90_verification_flags_verified: bool
    exact_readback_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def store_recovery_startup_replay_retained_identity_binding_receipt_replay_identity(
    evidence: RecoveryStartupReplayRetainedIdentityBindingReceiptReplayEvidence,
    *,
    destination_path: str | os.PathLike[str],
) -> RecoveryStartupReplayRetainedIdentityBindingReceiptReplayIdentityStoreEvidence:
    """Persist the minimal canonical identity of one compatible P90 replay."""
    if not isinstance(evidence, RecoveryStartupReplayRetainedIdentityBindingReceiptReplayEvidence):
        raise ValueError("P90 replay evidence has an incompatible type")
    if evidence.evidence_state != P90_EVIDENCE_STATE:
        raise ValueError("P90 replay evidence state is incompatible")
    if evidence.automatic_control_allowed is not False:
        raise ValueError("P90 replay evidence must not grant automatic-control authority")
    if any(getattr(evidence, flag, None) is not True for flag in _REQUIRED_VERIFICATION_FLAGS):
        raise ValueError("P90 replay evidence verification flags are incomplete")

    sequence = _positive_int(evidence.sequence, field="P90 sequence")
    lineage = _sha256(evidence.lineage_sha256, field="P90 lineage SHA-256")
    binding_receipt_sha = _sha256(evidence.binding_receipt_payload_sha256, field="P90 binding receipt payload SHA-256")
    binding_receipt_size = _positive_int(evidence.binding_receipt_payload_size_bytes, field="P90 binding receipt payload size")
    receipt_binding = _sha256(evidence.receipt_identity_binding_sha256, field="P90 receipt identity binding SHA-256")
    retained_sha = _sha256(evidence.retained_identity_payload_sha256, field="P90 retained identity payload SHA-256")
    retained_size = _positive_int(evidence.retained_identity_payload_size_bytes, field="P90 retained identity payload size")
    replay_stored_binding = _sha256(evidence.replay_stored_identity_binding_sha256, field="P90 replay/stored-identity binding SHA-256")
    replay_receipt_sha = _sha256(evidence.replay_binding_receipt_payload_sha256, field="P90 replay binding receipt payload SHA-256")
    replay_receipt_size = _positive_int(evidence.replay_binding_receipt_payload_size_bytes, field="P90 replay binding receipt payload size")
    retained_replay_sha = _sha256(evidence.retained_replay_identity_payload_sha256, field="P90 retained replay identity payload SHA-256")
    retained_replay_size = _positive_int(evidence.retained_replay_identity_payload_size_bytes, field="P90 retained replay identity payload size")
    replay_retained_binding = _sha256(evidence.replay_retained_identity_binding_sha256, field="P90 replay/retained-identity binding SHA-256")
    p89_receipt_sha = _sha256(
        evidence.replay_retained_identity_binding_receipt_payload_sha256,
        field="P90 replay/retained-identity binding receipt payload SHA-256",
    )
    p89_receipt_size = _positive_int(
        evidence.replay_retained_identity_binding_receipt_payload_size_bytes,
        field="P90 replay/retained-identity binding receipt payload size",
    )

    payload = {
        "binding_receipt_payload_sha256": binding_receipt_sha,
        "binding_receipt_payload_size_bytes": binding_receipt_size,
        "lineage_sha256": lineage,
        "p90_evidence_state": P90_EVIDENCE_STATE,
        "receipt_identity_binding_sha256": receipt_binding,
        "replay_binding_receipt_payload_sha256": replay_receipt_sha,
        "replay_binding_receipt_payload_size_bytes": replay_receipt_size,
        "replay_retained_identity_binding_receipt_payload_sha256": p89_receipt_sha,
        "replay_retained_identity_binding_receipt_payload_size_bytes": p89_receipt_size,
        "replay_retained_identity_binding_sha256": replay_retained_binding,
        "replay_stored_identity_binding_sha256": replay_stored_binding,
        "retained_identity_payload_sha256": retained_sha,
        "retained_identity_payload_size_bytes": retained_size,
        "retained_replay_identity_payload_sha256": retained_replay_sha,
        "retained_replay_identity_payload_size_bytes": retained_replay_size,
        "sequence": sequence,
    }
    encoded = _canonical(payload)
    encoded_sha = hashlib.sha256(encoded).hexdigest()

    destination = Path(destination_path)
    if not destination.name:
        raise ValueError("destination path must identify a file")
    destination.parent.mkdir(parents=True, exist_ok=True)

    fd, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
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
        raise ValueError("stored P90 replay identity differs from published bytes")
    if hashlib.sha256(stored).hexdigest() != encoded_sha:
        raise ValueError("stored P90 replay identity SHA-256 mismatch")

    return RecoveryStartupReplayRetainedIdentityBindingReceiptReplayIdentityStoreEvidence(
        sequence=sequence,
        lineage_sha256=lineage,
        binding_receipt_payload_sha256=binding_receipt_sha,
        binding_receipt_payload_size_bytes=binding_receipt_size,
        receipt_identity_binding_sha256=receipt_binding,
        retained_identity_payload_sha256=retained_sha,
        retained_identity_payload_size_bytes=retained_size,
        replay_stored_identity_binding_sha256=replay_stored_binding,
        replay_binding_receipt_payload_sha256=replay_receipt_sha,
        replay_binding_receipt_payload_size_bytes=replay_receipt_size,
        retained_replay_identity_payload_sha256=retained_replay_sha,
        retained_replay_identity_payload_size_bytes=retained_replay_size,
        replay_retained_identity_binding_sha256=replay_retained_binding,
        replay_retained_identity_binding_receipt_payload_sha256=p89_receipt_sha,
        replay_retained_identity_binding_receipt_payload_size_bytes=p89_receipt_size,
        stored_payload_sha256=encoded_sha,
        stored_payload_size_bytes=len(encoded),
        destination_path=str(destination),
        p90_evidence_state_verified=True,
        p90_verification_flags_verified=True,
        exact_readback_verified=True,
    )
