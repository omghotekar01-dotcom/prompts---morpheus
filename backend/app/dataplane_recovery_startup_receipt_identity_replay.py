"""Replay-verify one locally persisted P76 startup-admission identity record.

P77 closes the consumer-side seam left explicit by P76. A caller supplies P76
store evidence and the path of the persisted identity record. This gate verifies
the exact stored byte identity, strict canonical JSON encoding, and semantic
agreement with the P76 evidence before emitting read-only replay evidence.

The verification is deliberately local and historical. It does not authenticate
the record, establish freshness or monotonicity, prevent rollback/replay, or
authorize startup or mutation.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from .dataplane_recovery_startup_receipt_identity_store import (
    EVIDENCE_STATE as P76_EVIDENCE_STATE,
    RecoveryStartupReceiptIdentityStoreEvidence,
)
from .dataplane_recovery_startup_receipt_replay import (
    EVIDENCE_STATE as P75_EVIDENCE_STATE,
)

EVIDENCE_STATE = "LOCAL_DATA_PLANE_RECOVERY_STARTUP_ADMISSION_RECEIPT_IDENTITY_REPLAY_VERIFIED"
TRUTH_BOUNDARY = (
    "This gate proves only that, during this call, one local P76 identity record existed at the selected path, matched the exact "
    "byte length and SHA-256 recorded by compatible P76 evidence, used the strict canonical JSON schema, and semantically matched "
    "that evidence. It does not authenticate the P76 evidence or filesystem record, establish freshness/latest/global-head truth or "
    "independent monotonicity, prevent rollback/replay/coordinated replacement, provide an atomic snapshot after return, rerun P67-P76, "
    "authorize startup or mutation, provide CAS, leases, fencing, TPM/HSM protection, remote witnessing, distributed consensus, HA, "
    "native-object recovery, cross-process hot swap, production readiness, benchmark evidence, novelty evidence, or automatic-control authority."
)

_REQUIRED_KEYS = {
    "admission_binding_sha256",
    "lineage_sha256",
    "p75_evidence_state",
    "receipt_payload_sha256",
    "receipt_payload_size_bytes",
    "sequence",
}


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
class RecoveryStartupReceiptIdentityReplayEvidence:
    sequence: int
    lineage_sha256: str
    receipt_payload_sha256: str
    receipt_payload_size_bytes: int
    admission_binding_sha256: str
    stored_payload_sha256: str
    stored_payload_size_bytes: int
    source_path: str
    expected_payload_identity_verified: bool
    canonical_record_verified: bool
    semantic_identity_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def replay_recovery_startup_receipt_identity(
    evidence: RecoveryStartupReceiptIdentityStoreEvidence,
    *,
    source_path: str | os.PathLike[str] | None = None,
) -> RecoveryStartupReceiptIdentityReplayEvidence:
    """Verify one persisted P76 identity record against compatible P76 evidence."""
    if not isinstance(evidence, RecoveryStartupReceiptIdentityStoreEvidence):
        raise ValueError("P76 identity-store evidence has an incompatible type")
    if evidence.evidence_state != P76_EVIDENCE_STATE:
        raise ValueError("P76 identity-store evidence state is incompatible")
    if evidence.automatic_control_allowed is not False:
        raise ValueError("P76 identity-store evidence must not grant automatic-control authority")
    if evidence.p75_evidence_state_verified is not True:
        raise ValueError("P76 P75-evidence-state verification is incomplete")
    if evidence.p75_verification_flags_verified is not True:
        raise ValueError("P76 P75 verification flags are incomplete")
    if evidence.exact_readback_verified is not True:
        raise ValueError("P76 exact-readback verification is incomplete")

    sequence = _positive_int(evidence.sequence, field="P76 sequence")
    lineage = _sha256(evidence.lineage_sha256, field="P76 lineage SHA-256")
    receipt_sha = _sha256(
        evidence.receipt_payload_sha256, field="P76 receipt payload SHA-256"
    )
    receipt_size = _positive_int(
        evidence.receipt_payload_size_bytes, field="P76 receipt payload size"
    )
    admission_binding = _sha256(
        evidence.admission_binding_sha256, field="P76 admission binding SHA-256"
    )
    expected_stored_sha = _sha256(
        evidence.stored_payload_sha256, field="P76 stored payload SHA-256"
    )
    expected_stored_size = _positive_int(
        evidence.stored_payload_size_bytes, field="P76 stored payload size"
    )

    source = Path(evidence.destination_path if source_path is None else source_path)
    if not source.name:
        raise ValueError("source path must identify a file")

    raw = source.read_bytes()
    if len(raw) != expected_stored_size:
        raise ValueError("stored startup-admission receipt identity byte length mismatch")
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha != expected_stored_sha:
        raise ValueError("stored startup-admission receipt identity SHA-256 mismatch")

    try:
        decoded = raw.decode("utf-8")
        payload = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("stored startup-admission receipt identity is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("stored startup-admission receipt identity must be a JSON object")
    if set(payload) != _REQUIRED_KEYS:
        raise ValueError("stored startup-admission receipt identity schema is incompatible")
    if _canonical(payload) != raw:
        raise ValueError("stored startup-admission receipt identity is not canonical JSON")

    if payload["sequence"] != sequence:
        raise ValueError("stored startup-admission receipt identity sequence mismatch")
    if payload["lineage_sha256"] != lineage:
        raise ValueError("stored startup-admission receipt identity lineage mismatch")
    if payload["receipt_payload_sha256"] != receipt_sha:
        raise ValueError("stored startup-admission receipt payload SHA-256 mismatch")
    if payload["receipt_payload_size_bytes"] != receipt_size:
        raise ValueError("stored startup-admission receipt payload size mismatch")
    if payload["admission_binding_sha256"] != admission_binding:
        raise ValueError("stored startup-admission receipt admission binding mismatch")
    if payload["p75_evidence_state"] != P75_EVIDENCE_STATE:
        raise ValueError("stored startup-admission receipt P75 evidence state mismatch")

    return RecoveryStartupReceiptIdentityReplayEvidence(
        sequence=sequence,
        lineage_sha256=lineage,
        receipt_payload_sha256=receipt_sha,
        receipt_payload_size_bytes=receipt_size,
        admission_binding_sha256=admission_binding,
        stored_payload_sha256=actual_sha,
        stored_payload_size_bytes=len(raw),
        source_path=str(source),
        expected_payload_identity_verified=True,
        canonical_record_verified=True,
        semantic_identity_verified=True,
    )
