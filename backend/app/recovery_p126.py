"""Persist the minimum verified P125 canonical P124-replay identity locally.

P126 closes only the local-retention seam left explicit by P125. A caller supplies
verified P125 replay evidence; this gate validates that evidence contract, reduces
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
from dataclasses import make_dataclass
from pathlib import Path

from .recovery_p125 import (
    EVIDENCE_STATE as P125_EVIDENCE_STATE,
    RecoveryP124ReplayEvidence,
    _FIELDS as P125_RECEIPT_FIELDS,
)

EVIDENCE_STATE = P125_EVIDENCE_STATE + "_IDENTITY_STORED"
TRUTH_BOUNDARY = (
    "This gate proves only that compatible verified P125 replay evidence was reduced to a strict canonical local identity record, "
    "written through a same-directory temporary file, fsynced, atomically replaced at the selected path, and read back with exact "
    "byte identity during this call. The file is local historical evidence, not an authenticated, freshness-bearing, or independently "
    "monotonic trust anchor. This gate does not authenticate P125 evidence or the filesystem, prove freshness/latest/global/monotonic "
    "head truth, prevent rollback/replay or coordinated replacement, rerun P124/P125 or dependencies, authorize startup or mutation, "
    "provide universal crash or power-loss durability, CAS, leases, fencing, TPM/HSM protection, remote witnessing, distributed consensus, "
    "HA, native-object recovery, cross-process hot swap, production readiness, benchmark evidence, novelty evidence, or automatic-control authority."
)

_FIELDS = (
    *P125_RECEIPT_FIELDS,
    ("p124_receipt_payload_sha256", "sha"),
    ("p124_receipt_payload_size_bytes", "int"),
)
_REQUIRED_VERIFICATION_FLAGS = (
    "expected_payload_identity_verified",
    "canonical_receipt_verified",
    "dependency_state_verified",
    "p120_p122_composition_binding_recomputed_verified",
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


RecoveryP125ReplayIdentityStoreEvidence = make_dataclass(
    "RecoveryP125ReplayIdentityStoreEvidence",
    [
        *((field, int if kind == "int" else str) for field, kind in _FIELDS),
        ("stored_payload_sha256", str),
        ("stored_payload_size_bytes", int),
        ("destination_path", str),
        ("p125_evidence_state_verified", bool),
        ("p125_verification_flags_verified", bool),
        ("exact_readback_verified", bool),
        ("evidence_state", str, EVIDENCE_STATE),
        ("automatic_control_allowed", bool, False),
    ],
    frozen=True,
    namespace={"as_dict": lambda self: {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}},
)


def store_p125_replay_identity(
    evidence: RecoveryP124ReplayEvidence,
    *,
    destination_path: str | os.PathLike[str],
) -> RecoveryP125ReplayIdentityStoreEvidence:
    """Persist the minimal canonical identity of one compatible P125 replay."""
    if not isinstance(evidence, RecoveryP124ReplayEvidence):
        raise ValueError("P125 replay evidence has an incompatible type")
    if evidence.evidence_state != P125_EVIDENCE_STATE:
        raise ValueError("P125 replay evidence state is incompatible")
    if evidence.automatic_control_allowed is not False:
        raise ValueError("P125 replay evidence must not grant automatic-control authority")
    if any(getattr(evidence, flag, None) is not True for flag in _REQUIRED_VERIFICATION_FLAGS):
        raise ValueError("P125 replay evidence verification flags are incomplete")

    values: dict[str, object] = {}
    for field, kind in _FIELDS:
        raw = getattr(evidence, field, None)
        values[field] = (
            _positive_int(raw, field=f"P125 {field}")
            if kind == "int"
            else _sha256(raw, field=f"P125 {field}")
        )

    payload = {**values, "p125_evidence_state": P125_EVIDENCE_STATE}
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
        raise ValueError("stored P125 replay identity differs from published bytes")
    if hashlib.sha256(stored).hexdigest() != encoded_sha:
        raise ValueError("stored P125 replay identity SHA-256 mismatch")

    return RecoveryP125ReplayIdentityStoreEvidence(
        **values,
        stored_payload_sha256=encoded_sha,
        stored_payload_size_bytes=len(encoded),
        destination_path=str(destination),
        p125_evidence_state_verified=True,
        p125_verification_flags_verified=True,
        exact_readback_verified=True,
    )
