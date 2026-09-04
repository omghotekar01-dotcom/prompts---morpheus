"""Replay-verify the locally retained P86 P85-replay identity record.

P87 independently reopens the P86 record and verifies exact byte identity,
strict canonical JSON, exact schema, the embedded P85 evidence-state identity,
and semantic agreement with the P86 evidence supplied by the caller.

This is historical read-only evidence. It does not authenticate the filesystem,
prove freshness or monotonicity, prevent coordinated rollback/replay, or
authorize startup or mutation.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store import (
    EVIDENCE_STATE as P86_EVIDENCE_STATE,
    RecoveryStartupReplayStoredIdentityBindingReceiptReplayIdentityStoreEvidence,
)
from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay import (
    EVIDENCE_STATE as P85_EVIDENCE_STATE,
)

EVIDENCE_STATE = (
    "LOCAL_DATA_PLANE_RECOVERY_STARTUP_ADMISSION_STORED_RECEIPT_BINDING_RECEIPT_REPLAY_STORED_IDENTITY_BINDING_RECEIPT_REPLAY_IDENTITY_STORED_REPLAY_VERIFIED"
)
TRUTH_BOUNDARY = (
    "This historical read-only gate proves only that one selected local P86 record matched the caller-supplied P86 evidence during "
    "this call: exact stored byte length and SHA-256, strict canonical JSON, exact schema, embedded P85 evidence-state identity, and "
    "semantic fields were verified. It does not authenticate P86 evidence or the filesystem, prove freshness/latest/global/monotonic "
    "head truth, prevent replay/rollback or coordinated replacement, provide an atomic snapshot after return, rerun P85/P86 or their "
    "dependencies, authorize startup or mutation, provide CAS, leases, fencing, TPM/HSM protection, remote witnessing, distributed "
    "consensus, HA, native-object recovery, cross-process hot swap, production readiness, benchmark evidence, novelty evidence, or "
    "automatic-control authority."
)

_REQUIRED_P86_FLAGS = (
    "p85_evidence_state_verified",
    "p85_verification_flags_verified",
    "exact_readback_verified",
)
_SCHEMA_KEYS = frozenset(
    {
        "binding_receipt_payload_sha256",
        "binding_receipt_payload_size_bytes",
        "lineage_sha256",
        "p85_evidence_state",
        "receipt_identity_binding_sha256",
        "replay_binding_receipt_payload_sha256",
        "replay_binding_receipt_payload_size_bytes",
        "replay_stored_identity_binding_sha256",
        "retained_identity_payload_sha256",
        "retained_identity_payload_size_bytes",
        "sequence",
    }
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
class RecoveryStartupReplayStoredIdentityBindingReceiptReplayIdentityStoreReplayEvidence:
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
    stored_payload_sha256: str
    stored_payload_size_bytes: int
    source_path: str
    p86_evidence_state_verified: bool
    p86_verification_flags_verified: bool
    exact_payload_identity_verified: bool
    canonical_record_verified: bool
    semantic_agreement_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def verify_recovery_startup_replay_stored_identity_binding_receipt_replay_identity_store(
    evidence: RecoveryStartupReplayStoredIdentityBindingReceiptReplayIdentityStoreEvidence,
    *,
    source_path: str | os.PathLike[str] | None = None,
) -> RecoveryStartupReplayStoredIdentityBindingReceiptReplayIdentityStoreReplayEvidence:
    """Replay-verify one retained P86 identity record against compatible P86 evidence."""
    if not isinstance(evidence, RecoveryStartupReplayStoredIdentityBindingReceiptReplayIdentityStoreEvidence):
        raise ValueError("P86 stored replay identity evidence has an incompatible type")
    if evidence.evidence_state != P86_EVIDENCE_STATE:
        raise ValueError("P86 stored replay identity evidence state is incompatible")
    if evidence.automatic_control_allowed is not False:
        raise ValueError("P86 stored replay identity evidence must not grant automatic-control authority")
    if any(getattr(evidence, flag, None) is not True for flag in _REQUIRED_P86_FLAGS):
        raise ValueError("P86 stored replay identity verification flags are incomplete")

    sequence = _positive_int(evidence.sequence, field="P86 sequence")
    lineage = _sha256(evidence.lineage_sha256, field="P86 lineage SHA-256")
    binding_receipt_sha = _sha256(evidence.binding_receipt_payload_sha256, field="P86 binding receipt payload SHA-256")
    binding_receipt_size = _positive_int(evidence.binding_receipt_payload_size_bytes, field="P86 binding receipt payload size")
    receipt_binding = _sha256(evidence.receipt_identity_binding_sha256, field="P86 receipt identity binding SHA-256")
    retained_sha = _sha256(evidence.retained_identity_payload_sha256, field="P86 retained identity payload SHA-256")
    retained_size = _positive_int(evidence.retained_identity_payload_size_bytes, field="P86 retained identity payload size")
    replay_binding = _sha256(evidence.replay_stored_identity_binding_sha256, field="P86 replay/stored-identity binding SHA-256")
    replay_receipt_sha = _sha256(evidence.replay_binding_receipt_payload_sha256, field="P86 replay binding receipt payload SHA-256")
    replay_receipt_size = _positive_int(evidence.replay_binding_receipt_payload_size_bytes, field="P86 replay binding receipt payload size")
    stored_sha = _sha256(evidence.stored_payload_sha256, field="P86 stored payload SHA-256")
    stored_size = _positive_int(evidence.stored_payload_size_bytes, field="P86 stored payload size")

    source = Path(evidence.destination_path if source_path is None else source_path)
    if not source.name:
        raise ValueError("source path must identify a file")
    raw = source.read_bytes()
    if len(raw) != stored_size:
        raise ValueError("retained P86 record byte length differs from P86 evidence")
    if hashlib.sha256(raw).hexdigest() != stored_sha:
        raise ValueError("retained P86 record SHA-256 differs from P86 evidence")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("retained P86 record is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("retained P86 record must be a JSON object")
    if set(payload) != _SCHEMA_KEYS:
        raise ValueError("retained P86 record schema is incompatible")
    if _canonical(payload) != raw:
        raise ValueError("retained P86 record is not strict canonical JSON")
    if payload["p85_evidence_state"] != P85_EVIDENCE_STATE:
        raise ValueError("retained P86 record embeds an incompatible P85 evidence state")

    expected = {
        "binding_receipt_payload_sha256": binding_receipt_sha,
        "binding_receipt_payload_size_bytes": binding_receipt_size,
        "lineage_sha256": lineage,
        "p85_evidence_state": P85_EVIDENCE_STATE,
        "receipt_identity_binding_sha256": receipt_binding,
        "replay_binding_receipt_payload_sha256": replay_receipt_sha,
        "replay_binding_receipt_payload_size_bytes": replay_receipt_size,
        "replay_stored_identity_binding_sha256": replay_binding,
        "retained_identity_payload_sha256": retained_sha,
        "retained_identity_payload_size_bytes": retained_size,
        "sequence": sequence,
    }
    if payload != expected:
        raise ValueError("retained P86 record semantics differ from P86 evidence")

    return RecoveryStartupReplayStoredIdentityBindingReceiptReplayIdentityStoreReplayEvidence(
        sequence=sequence,
        lineage_sha256=lineage,
        binding_receipt_payload_sha256=binding_receipt_sha,
        binding_receipt_payload_size_bytes=binding_receipt_size,
        receipt_identity_binding_sha256=receipt_binding,
        retained_identity_payload_sha256=retained_sha,
        retained_identity_payload_size_bytes=retained_size,
        replay_stored_identity_binding_sha256=replay_binding,
        replay_binding_receipt_payload_sha256=replay_receipt_sha,
        replay_binding_receipt_payload_size_bytes=replay_receipt_size,
        stored_payload_sha256=stored_sha,
        stored_payload_size_bytes=stored_size,
        source_path=str(source),
        p86_evidence_state_verified=True,
        p86_verification_flags_verified=True,
        exact_payload_identity_verified=True,
        canonical_record_verified=True,
        semantic_agreement_verified=True,
    )
