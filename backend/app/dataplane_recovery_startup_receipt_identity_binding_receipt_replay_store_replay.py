"""Replay-verify one locally retained P81 P80-replay identity record.

P82 closes the consumer-side seam left explicit by P81. A caller supplies P81
store evidence and, optionally, the retained record path. This gate verifies the
exact stored byte identity, strict canonical JSON encoding, and semantic
agreement with the P81 evidence before emitting read-only replay evidence.

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

from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay import (
    EVIDENCE_STATE as P80_EVIDENCE_STATE,
)
from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store import (
    EVIDENCE_STATE as P81_EVIDENCE_STATE,
    RecoveryStartupStoredReceiptBindingReceiptReplayIdentityStoreEvidence,
)

EVIDENCE_STATE = (
    "LOCAL_DATA_PLANE_RECOVERY_STARTUP_ADMISSION_STORED_RECEIPT_BINDING_RECEIPT_REPLAY_IDENTITY_REPLAY_VERIFIED"
)
TRUTH_BOUNDARY = (
    "This read-only historical gate proves only that, during this call, one local P81 retained P80-replay identity record existed at the selected "
    "path, matched the exact byte length and SHA-256 recorded by compatible P81 evidence, used the strict canonical JSON schema, and "
    "semantically matched that evidence. It does not authenticate the P81 evidence or filesystem record, establish freshness/latest/"
    "global/monotonic head truth or independent monotonicity, prevent rollback/replay/coordinated replacement, provide an atomic snapshot "
    "after return, rerun P79-P81 or their dependencies, authorize startup or mutation, provide CAS, leases, fencing, TPM/HSM protection, "
    "remote witnessing, distributed consensus, HA, native-object recovery, cross-process hot swap, production readiness, benchmark "
    "evidence, novelty evidence, or automatic-control authority."
)

_REQUIRED_KEYS = {
    "binding_receipt_payload_sha256",
    "binding_receipt_payload_size_bytes",
    "lineage_sha256",
    "p80_evidence_state",
    "receipt_identity_binding_sha256",
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
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


@dataclass(frozen=True)
class RecoveryStartupStoredReceiptBindingReceiptReplayIdentityReplayEvidence:
    sequence: int
    lineage_sha256: str
    binding_receipt_payload_sha256: str
    binding_receipt_payload_size_bytes: int
    receipt_identity_binding_sha256: str
    stored_payload_sha256: str
    stored_payload_size_bytes: int
    source_path: str
    expected_payload_identity_verified: bool
    canonical_record_verified: bool
    p80_evidence_state_verified: bool
    semantic_identity_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def replay_recovery_startup_stored_receipt_binding_receipt_replay_identity(
    evidence: RecoveryStartupStoredReceiptBindingReceiptReplayIdentityStoreEvidence,
    *,
    source_path: str | os.PathLike[str] | None = None,
) -> RecoveryStartupStoredReceiptBindingReceiptReplayIdentityReplayEvidence:
    """Verify one persisted P81 identity record against compatible P81 evidence."""
    if not isinstance(evidence, RecoveryStartupStoredReceiptBindingReceiptReplayIdentityStoreEvidence):
        raise ValueError("P81 identity-store evidence has an incompatible type")
    if evidence.evidence_state != P81_EVIDENCE_STATE:
        raise ValueError("P81 identity-store evidence state is incompatible")
    if evidence.automatic_control_allowed is not False:
        raise ValueError("P81 identity-store evidence must not grant automatic-control authority")
    if evidence.p80_evidence_state_verified is not True:
        raise ValueError("P81 P80-evidence-state verification is incomplete")
    if evidence.p80_verification_flags_verified is not True:
        raise ValueError("P81 P80 verification flags are incomplete")
    if evidence.exact_readback_verified is not True:
        raise ValueError("P81 exact-readback verification is incomplete")

    sequence = _positive_int(evidence.sequence, field="P81 sequence")
    lineage = _sha256(evidence.lineage_sha256, field="P81 lineage SHA-256")
    binding_receipt_sha = _sha256(
        evidence.binding_receipt_payload_sha256,
        field="P81 binding receipt payload SHA-256",
    )
    binding_receipt_size = _positive_int(
        evidence.binding_receipt_payload_size_bytes,
        field="P81 binding receipt payload size",
    )
    receipt_identity_binding = _sha256(
        evidence.receipt_identity_binding_sha256,
        field="P81 receipt identity binding SHA-256",
    )
    expected_stored_sha = _sha256(
        evidence.stored_payload_sha256,
        field="P81 stored payload SHA-256",
    )
    expected_stored_size = _positive_int(
        evidence.stored_payload_size_bytes,
        field="P81 stored payload size",
    )

    source = Path(evidence.destination_path if source_path is None else source_path)
    if not source.name:
        raise ValueError("source path must identify a file")

    raw = source.read_bytes()
    if len(raw) != expected_stored_size:
        raise ValueError("stored P80 replay identity byte length mismatch")
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha != expected_stored_sha:
        raise ValueError("stored P80 replay identity SHA-256 mismatch")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("stored P80 replay identity is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("stored P80 replay identity must be a JSON object")
    if set(payload) != _REQUIRED_KEYS:
        raise ValueError("stored P80 replay identity schema is incompatible")
    if _canonical(payload) != raw:
        raise ValueError("stored P80 replay identity is not canonical JSON")

    if payload["sequence"] != sequence:
        raise ValueError("stored P80 replay identity sequence mismatch")
    if payload["lineage_sha256"] != lineage:
        raise ValueError("stored P80 replay identity lineage mismatch")
    if payload["binding_receipt_payload_sha256"] != binding_receipt_sha:
        raise ValueError("stored P80 replay binding receipt SHA-256 mismatch")
    if payload["binding_receipt_payload_size_bytes"] != binding_receipt_size:
        raise ValueError("stored P80 replay binding receipt size mismatch")
    if payload["receipt_identity_binding_sha256"] != receipt_identity_binding:
        raise ValueError("stored P80 replay receipt identity binding mismatch")
    if payload["p80_evidence_state"] != P80_EVIDENCE_STATE:
        raise ValueError("stored P80 replay P80 evidence state mismatch")

    return RecoveryStartupStoredReceiptBindingReceiptReplayIdentityReplayEvidence(
        sequence=sequence,
        lineage_sha256=lineage,
        binding_receipt_payload_sha256=binding_receipt_sha,
        binding_receipt_payload_size_bytes=binding_receipt_size,
        receipt_identity_binding_sha256=receipt_identity_binding,
        stored_payload_sha256=actual_sha,
        stored_payload_size_bytes=len(raw),
        source_path=str(source),
        expected_payload_identity_verified=True,
        canonical_record_verified=True,
        p80_evidence_state_verified=True,
        semantic_identity_verified=True,
    )
