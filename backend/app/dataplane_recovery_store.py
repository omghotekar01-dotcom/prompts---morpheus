"""Local filesystem publication gate for canonical MORPHEUS recovery payloads.

P61 adds a narrow startup-grade persistence boundary after P59/P60: a canonical
P59 payload can be published to one caller-selected local file and read back with
content-addressed integrity checks. This module intentionally does not claim
power-loss crash consistency, HA, replication, distributed coordination, or
native-object recovery.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from .dataplane_recovery_interchange import EVIDENCE_STATE as P59_EVIDENCE_STATE
from .dataplane_recovery_interchange import import_recovery_checkpoint

EVIDENCE_STATE = "LOCAL_DATA_PLANE_RECOVERY_STORE_CONSISTENCY_VERIFIED"
TRUTH_BOUNDARY = (
    "This gate proves only that one exact canonical P59 recovery payload was validated, published to a caller-selected "
    "local filesystem path using same-directory temporary-file replacement, and read back byte-for-byte with matching "
    "SHA-256 identity. It does not prove power-loss crash consistency, filesystem or hardware durability, replication, "
    "HA, distributed coordination, native-object restoration, cross-process hot swap, production readiness or performance."
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_payload(payload: bytes) -> tuple[str, int]:
    checkpoint, interchange = import_recovery_checkpoint(payload)
    if interchange.evidence_state != P59_EVIDENCE_STATE:
        raise ValueError("P59 interchange evidence has an incompatible evidence state")
    if not interchange.canonical_roundtrip_verified:
        raise ValueError("P59 interchange evidence is not canonically verified")
    if interchange.automatic_control_allowed:
        raise ValueError("P59 interchange evidence cannot authorize automatic control")
    if interchange.checkpoint_sha256 != checkpoint.checkpoint_sha256:
        raise ValueError("P59 interchange evidence checkpoint identity drift")
    if interchange.payload_sha256 != _sha256(payload) or interchange.payload_size_bytes != len(payload):
        raise ValueError("P59 interchange evidence payload identity drift")
    return checkpoint.checkpoint_sha256, interchange.payload_size_bytes


@dataclass(frozen=True)
class RecoveryStoreEvidence:
    checkpoint_sha256: str
    payload_sha256: str
    payload_size_bytes: int
    canonical_interchange_verified: bool
    same_directory_replace_used: bool
    readback_identity_verified: bool
    store_consistency_verified: bool
    p59_evidence_state: str
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {**self.__dict__, "truth_boundary": TRUTH_BOUNDARY}


def publish_recovery_payload(path: str | os.PathLike[str], payload: bytes) -> RecoveryStoreEvidence:
    """Validate, publish, and byte-verify one canonical P59 payload locally."""
    checkpoint_sha256, payload_size = _validate_payload(payload)
    target = Path(path)
    if not target.name:
        raise ValueError("recovery store path must name a file")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.morpheus-tmp-{os.getpid()}")
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
        raise ValueError("recovery store readback differs from published payload")
    # Re-parse the bytes actually read from storage, not merely the caller input.
    _validate_payload(readback)
    return RecoveryStoreEvidence(
        checkpoint_sha256=checkpoint_sha256,
        payload_sha256=_sha256(readback),
        payload_size_bytes=payload_size,
        canonical_interchange_verified=True,
        same_directory_replace_used=True,
        readback_identity_verified=True,
        store_consistency_verified=True,
        p59_evidence_state=P59_EVIDENCE_STATE,
    )


def load_recovery_payload(
    path: str | os.PathLike[str], *, expected_payload_sha256: str | None = None
) -> bytes:
    """Load canonical P59 bytes and optionally require an expected content identity."""
    payload = Path(path).read_bytes()
    _validate_payload(payload)
    actual = _sha256(payload)
    if expected_payload_sha256 is not None:
        expected = expected_payload_sha256.strip().casefold()
        if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
            raise ValueError("expected_payload_sha256 must be a 64-character hexadecimal digest")
        if actual != expected:
            raise ValueError("recovery store payload SHA-256 does not match expected identity")
    return payload
