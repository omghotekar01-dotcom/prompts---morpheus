"""Replay-verify the locally retained P91 P90-replay identity record.

P92 independently reopens the P91 record and verifies exact byte identity,
strict canonical JSON, exact schema, the embedded P90 evidence-state identity,
and semantic agreement with the P91 evidence supplied by the caller.

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

from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay import (
    EVIDENCE_STATE as P90_EVIDENCE_STATE,
)
from .dataplane_recovery_startup_receipt_identity_binding_receipt_replay_store_replay_binding_receipt_replay_store_replay_binding_receipt_replay_store import (
    EVIDENCE_STATE as P91_EVIDENCE_STATE,
    RecoveryStartupReplayRetainedIdentityBindingReceiptReplayIdentityStoreEvidence,
)

EVIDENCE_STATE = (
    "LOCAL_DATA_PLANE_RECOVERY_STARTUP_ADMISSION_STORED_RECEIPT_BINDING_RECEIPT_REPLAY_STORED_IDENTITY_BINDING_"
    "RECEIPT_REPLAY_IDENTITY_STORED_REPLAY_BINDING_RECEIPT_REPLAY_VERIFIED_IDENTITY_STORED_REPLAY_VERIFIED"
)
TRUTH_BOUNDARY = (
    "This historical read-only gate proves only that one selected local P91 record matched the caller-supplied P91 evidence during "
    "this call: exact stored byte length and SHA-256, strict canonical JSON, exact schema, embedded P90 evidence-state identity, and "
    "semantic fields were verified. It does not authenticate P91 evidence or the filesystem, prove freshness/latest/global/monotonic "
    "head truth, prevent replay/rollback or coordinated replacement, provide an atomic snapshot after return, rerun P90/P91 or their "
    "dependencies, authorize startup or mutation, provide CAS, leases, fencing, TPM/HSM protection, remote witnessing, distributed "
    "consensus, HA, native-object recovery, cross-process hot swap, production readiness, benchmark evidence, novelty evidence, or "
    "automatic-control authority."
)

_REQUIRED_P91_FLAGS = (
    "p90_evidence_state_verified",
    "p90_verification_flags_verified",
    "exact_readback_verified",
)
_SCHEMA_KEYS = frozenset(
    {
        "binding_receipt_payload_sha256",
        "binding_receipt_payload_size_bytes",
        "lineage_sha256",
        "p90_evidence_state",
        "receipt_identity_binding_sha256",
        "replay_binding_receipt_payload_sha256",
        "replay_binding_receipt_payload_size_bytes",
        "replay_retained_identity_binding_receipt_payload_sha256",
        "replay_retained_identity_binding_receipt_payload_size_bytes",
        "replay_retained_identity_binding_sha256",
        "replay_stored_identity_binding_sha256",
        "retained_identity_payload_sha256",
        "retained_identity_payload_size_bytes",
        "retained_replay_identity_payload_sha256",
        "retained_replay_identity_payload_size_bytes",
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
class RecoveryStartupReplayRetainedIdentityBindingReceiptReplayIdentityStoreReplayEvidence:
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
    source_path: str
    p91_evidence_state_verified: bool
    p91_verification_flags_verified: bool
    exact_payload_identity_verified: bool
    canonical_record_verified: bool
    semantic_agreement_verified: bool
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def verify_recovery_startup_replay_retained_identity_binding_receipt_replay_identity_store(
    evidence: RecoveryStartupReplayRetainedIdentityBindingReceiptReplayIdentityStoreEvidence,
    *,
    source_path: str | os.PathLike[str] | None = None,
) -> RecoveryStartupReplayRetainedIdentityBindingReceiptReplayIdentityStoreReplayEvidence:
    """Replay-verify one retained P91 identity record against compatible P91 evidence."""
    if not isinstance(evidence, RecoveryStartupReplayRetainedIdentityBindingReceiptReplayIdentityStoreEvidence):
        raise ValueError("P91 stored replay identity evidence has an incompatible type")
    if evidence.evidence_state != P91_EVIDENCE_STATE:
        raise ValueError("P91 stored replay identity evidence state is incompatible")
    if evidence.automatic_control_allowed is not False:
        raise ValueError("P91 stored replay identity evidence must not grant automatic-control authority")
    if any(getattr(evidence, flag, None) is not True for flag in _REQUIRED_P91_FLAGS):
        raise ValueError("P91 stored replay identity verification flags are incomplete")

    sequence = _positive_int(evidence.sequence, field="P91 sequence")
    lineage = _sha256(evidence.lineage_sha256, field="P91 lineage SHA-256")
    binding_receipt_sha = _sha256(evidence.binding_receipt_payload_sha256, field="P91 binding receipt payload SHA-256")
    binding_receipt_size = _positive_int(evidence.binding_receipt_payload_size_bytes, field="P91 binding receipt payload size")
    receipt_binding = _sha256(evidence.receipt_identity_binding_sha256, field="P91 receipt identity binding SHA-256")
    retained_sha = _sha256(evidence.retained_identity_payload_sha256, field="P91 retained identity payload SHA-256")
    retained_size = _positive_int(evidence.retained_identity_payload_size_bytes, field="P91 retained identity payload size")
    replay_stored_binding = _sha256(evidence.replay_stored_identity_binding_sha256, field="P91 replay/stored-identity binding SHA-256")
    replay_receipt_sha = _sha256(evidence.replay_binding_receipt_payload_sha256, field="P91 replay binding receipt payload SHA-256")
    replay_receipt_size = _positive_int(evidence.replay_binding_receipt_payload_size_bytes, field="P91 replay binding receipt payload size")
    retained_replay_sha = _sha256(evidence.retained_replay_identity_payload_sha256, field="P91 retained replay identity payload SHA-256")
    retained_replay_size = _positive_int(evidence.retained_replay_identity_payload_size_bytes, field="P91 retained replay identity payload size")
    replay_retained_binding = _sha256(evidence.replay_retained_identity_binding_sha256, field="P91 replay/retained-identity binding SHA-256")
    p89_receipt_sha = _sha256(
        evidence.replay_retained_identity_binding_receipt_payload_sha256,
        field="P91 replay/retained-identity binding receipt payload SHA-256",
    )
    p89_receipt_size = _positive_int(
        evidence.replay_retained_identity_binding_receipt_payload_size_bytes,
        field="P91 replay/retained-identity binding receipt payload size",
    )
    stored_sha = _sha256(evidence.stored_payload_sha256, field="P91 stored payload SHA-256")
    stored_size = _positive_int(evidence.stored_payload_size_bytes, field="P91 stored payload size")

    source = Path(evidence.destination_path if source_path is None else source_path)
    if not source.name:
        raise ValueError("source path must identify a file")
    raw = source.read_bytes()
    if len(raw) != stored_size:
        raise ValueError("retained P91 record byte length differs from P91 evidence")
    if hashlib.sha256(raw).hexdigest() != stored_sha:
        raise ValueError("retained P91 record SHA-256 differs from P91 evidence")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("retained P91 record is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("retained P91 record must be a JSON object")
    if set(payload) != _SCHEMA_KEYS:
        raise ValueError("retained P91 record schema is incompatible")
    if _canonical(payload) != raw:
        raise ValueError("retained P91 record is not strict canonical JSON")
    if payload["p90_evidence_state"] != P90_EVIDENCE_STATE:
        raise ValueError("retained P91 record embeds an incompatible P90 evidence state")

    expected = {
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
    if payload != expected:
        raise ValueError("retained P91 record semantics differ from P91 evidence")

    return RecoveryStartupReplayRetainedIdentityBindingReceiptReplayIdentityStoreReplayEvidence(
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
        stored_payload_sha256=stored_sha,
        stored_payload_size_bytes=stored_size,
        source_path=str(source),
        p91_evidence_state_verified=True,
        p91_verification_flags_verified=True,
        exact_payload_identity_verified=True,
        canonical_record_verified=True,
        semantic_agreement_verified=True,
    )
