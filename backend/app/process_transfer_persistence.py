from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .process_transfer_receipt import (
    ProcessTransferReceiptVerification,
    verify_process_transfer_admission_receipt,
)


BUNDLE_MAGIC = b"MORPHEUS_PROCESS_TRANSFER_EVIDENCE_BUNDLE_V1\n"
EVIDENCE_STATE = "VERIFIED_PROCESS_TRANSFER_EVIDENCE_PERSISTED_NO_ACTIVATION"
TRUTH_BOUNDARY = (
    "This receiver-side persistence gate proves only that already-admitted canonical receipt bytes and their exact "
    "identified logical snapshot bytes were verified before bundling, written through a same-directory temporary file, "
    "fsynced at the file level, atomically name-replaced where the host filesystem honors os.replace semantics, and "
    "re-read and re-verified by this process. It does not authenticate receipt origin, establish freshness/latest-head "
    "truth, prevent rollback/replay, provide a trusted monotonic counter, guarantee directory-entry or power-loss "
    "durability, provide filesystem/adversary isolation, decode records, restore native memory, launch/replace a process, "
    "authorize activation, provide fencing/leases/consensus/HA/SLA behavior, or establish performance, novelty, or "
    "production-readiness claims."
)


@dataclass(frozen=True)
class ProcessTransferBundleVerification:
    bundle_sha256: str
    bundle_size_bytes: int
    receipt_sha256: str
    snapshot_sha256: str
    snapshot_size_bytes: int
    migration_id: str
    session_id: str
    target_candidate_id: str
    target_artifact_sha256: str
    verification_manifest_sha256: str
    canonical_receipt_verified: bool = True
    snapshot_identity_verified: bool = True
    target_binding_verified: bool = True
    bundle_framing_verified: bool = True
    automatic_control_allowed: bool = False
    activation_allowed: bool = False
    truth_boundary: str = TRUTH_BOUNDARY


@dataclass(frozen=True)
class ProcessTransferPersistenceEvidence:
    path: str
    bundle_sha256: str
    bundle_size_bytes: int
    receipt_sha256: str
    snapshot_sha256: str
    file_fsync_completed: bool = True
    atomic_name_replace_completed: bool = True
    post_write_verification_completed: bool = True
    evidence_state: str = EVIDENCE_STATE
    automatic_control_allowed: bool = False
    activation_allowed: bool = False
    truth_boundary: str = TRUTH_BOUNDARY


def _require_bytes(value: Any, field: str) -> bytes:
    if not isinstance(value, bytes):
        raise TypeError(f"{field} must be bytes")
    return value


def _frame(value: bytes) -> bytes:
    return str(len(value)).encode("ascii") + b"\n" + value + b"\n"


def _parse_frame(bundle: bytes, offset: int, label: str) -> tuple[bytes, int]:
    newline = bundle.find(b"\n", offset)
    if newline < 0:
        raise ValueError(f"bundle {label} frame length is unterminated")
    raw_length = bundle[offset:newline]
    if not raw_length or len(raw_length) > 20 or any(ch < 48 or ch > 57 for ch in raw_length):
        raise ValueError(f"bundle {label} frame length is invalid")
    length = int(raw_length)
    start = newline + 1
    end = start + length
    if end >= len(bundle) or bundle[end : end + 1] != b"\n":
        raise ValueError(f"bundle {label} frame payload is truncated or malformed")
    return bundle[start:end], end + 1


def _verification_kwargs(
    *,
    expected_migration_id: str,
    expected_session_id: str,
    expected_target_candidate_id: str,
    expected_schema_identity: str,
    expected_codec_identity: str,
    expected_target_artifact_sha256: str,
    expected_verification_manifest_sha256: str,
) -> dict[str, str]:
    return {
        "expected_migration_id": expected_migration_id,
        "expected_session_id": expected_session_id,
        "expected_target_candidate_id": expected_target_candidate_id,
        "expected_schema_identity": expected_schema_identity,
        "expected_codec_identity": expected_codec_identity,
        "expected_target_artifact_sha256": expected_target_artifact_sha256,
        "expected_verification_manifest_sha256": expected_verification_manifest_sha256,
    }


def encode_process_transfer_evidence_bundle(
    receipt_bytes: bytes,
    snapshot_bytes: bytes,
    *,
    expected_migration_id: str,
    expected_session_id: str,
    expected_target_candidate_id: str,
    expected_schema_identity: str,
    expected_codec_identity: str,
    expected_target_artifact_sha256: str,
    expected_verification_manifest_sha256: str,
) -> bytes:
    """Bundle exact receipt + snapshot bytes only after fail-closed receipt replay succeeds."""

    receipt_bytes = _require_bytes(receipt_bytes, "receipt_bytes")
    snapshot_bytes = _require_bytes(snapshot_bytes, "snapshot_bytes")
    verify_process_transfer_admission_receipt(
        receipt_bytes,
        snapshot_bytes,
        **_verification_kwargs(
            expected_migration_id=expected_migration_id,
            expected_session_id=expected_session_id,
            expected_target_candidate_id=expected_target_candidate_id,
            expected_schema_identity=expected_schema_identity,
            expected_codec_identity=expected_codec_identity,
            expected_target_artifact_sha256=expected_target_artifact_sha256,
            expected_verification_manifest_sha256=expected_verification_manifest_sha256,
        ),
    )
    return BUNDLE_MAGIC + _frame(receipt_bytes) + _frame(snapshot_bytes)


def verify_process_transfer_evidence_bundle(
    bundle_bytes: bytes,
    *,
    expected_migration_id: str,
    expected_session_id: str,
    expected_target_candidate_id: str,
    expected_schema_identity: str,
    expected_codec_identity: str,
    expected_target_artifact_sha256: str,
    expected_verification_manifest_sha256: str,
) -> ProcessTransferBundleVerification:
    """Parse exact bundle framing and replay the embedded non-authoritative receipt."""

    bundle_bytes = _require_bytes(bundle_bytes, "bundle_bytes")
    if not bundle_bytes.startswith(BUNDLE_MAGIC):
        raise ValueError("process-transfer evidence bundle magic mismatch")
    offset = len(BUNDLE_MAGIC)
    receipt_bytes, offset = _parse_frame(bundle_bytes, offset, "receipt")
    snapshot_bytes, offset = _parse_frame(bundle_bytes, offset, "snapshot")
    if offset != len(bundle_bytes):
        raise ValueError("process-transfer evidence bundle has trailing bytes")

    receipt: ProcessTransferReceiptVerification = verify_process_transfer_admission_receipt(
        receipt_bytes,
        snapshot_bytes,
        **_verification_kwargs(
            expected_migration_id=expected_migration_id,
            expected_session_id=expected_session_id,
            expected_target_candidate_id=expected_target_candidate_id,
            expected_schema_identity=expected_schema_identity,
            expected_codec_identity=expected_codec_identity,
            expected_target_artifact_sha256=expected_target_artifact_sha256,
            expected_verification_manifest_sha256=expected_verification_manifest_sha256,
        ),
    )
    return ProcessTransferBundleVerification(
        bundle_sha256=hashlib.sha256(bundle_bytes).hexdigest(),
        bundle_size_bytes=len(bundle_bytes),
        receipt_sha256=receipt.receipt_sha256,
        snapshot_sha256=receipt.snapshot_sha256,
        snapshot_size_bytes=receipt.snapshot_size_bytes,
        migration_id=receipt.migration_id,
        session_id=receipt.session_id,
        target_candidate_id=receipt.target_candidate_id,
        target_artifact_sha256=receipt.target_artifact_sha256,
        verification_manifest_sha256=receipt.verification_manifest_sha256,
    )


def persist_process_transfer_evidence_bundle(
    path: str | os.PathLike[str],
    receipt_bytes: bytes,
    snapshot_bytes: bytes,
    *,
    expected_migration_id: str,
    expected_session_id: str,
    expected_target_candidate_id: str,
    expected_schema_identity: str,
    expected_codec_identity: str,
    expected_target_artifact_sha256: str,
    expected_verification_manifest_sha256: str,
) -> ProcessTransferPersistenceEvidence:
    """Verify, stage, file-fsync, replace, then re-read and re-verify an evidence bundle."""

    target = Path(path)
    parent = target.parent
    if not parent.exists():
        raise FileNotFoundError(f"process-transfer evidence parent directory does not exist: {parent}")
    if not parent.is_dir():
        raise NotADirectoryError(f"process-transfer evidence parent is not a directory: {parent}")

    kwargs = _verification_kwargs(
        expected_migration_id=expected_migration_id,
        expected_session_id=expected_session_id,
        expected_target_candidate_id=expected_target_candidate_id,
        expected_schema_identity=expected_schema_identity,
        expected_codec_identity=expected_codec_identity,
        expected_target_artifact_sha256=expected_target_artifact_sha256,
        expected_verification_manifest_sha256=expected_verification_manifest_sha256,
    )
    bundle = encode_process_transfer_evidence_bundle(receipt_bytes, snapshot_bytes, **kwargs)
    expected_hash = hashlib.sha256(bundle).hexdigest()

    fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(bundle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        finally:
            raise

    persisted = target.read_bytes()
    verification = verify_process_transfer_evidence_bundle(persisted, **kwargs)
    if verification.bundle_sha256 != expected_hash or persisted != bundle:
        raise ValueError("persisted process-transfer evidence bytes differ from verified staged bytes")

    return ProcessTransferPersistenceEvidence(
        path=str(target),
        bundle_sha256=verification.bundle_sha256,
        bundle_size_bytes=verification.bundle_size_bytes,
        receipt_sha256=verification.receipt_sha256,
        snapshot_sha256=verification.snapshot_sha256,
    )


def load_process_transfer_evidence_bundle(
    path: str | os.PathLike[str],
    *,
    expected_migration_id: str,
    expected_session_id: str,
    expected_target_candidate_id: str,
    expected_schema_identity: str,
    expected_codec_identity: str,
    expected_target_artifact_sha256: str,
    expected_verification_manifest_sha256: str,
) -> ProcessTransferBundleVerification:
    """Read persisted bytes and re-run complete framing + receipt/snapshot verification."""

    return verify_process_transfer_evidence_bundle(
        Path(path).read_bytes(),
        **_verification_kwargs(
            expected_migration_id=expected_migration_id,
            expected_session_id=expected_session_id,
            expected_target_candidate_id=expected_target_candidate_id,
            expected_schema_identity=expected_schema_identity,
            expected_codec_identity=expected_codec_identity,
            expected_target_artifact_sha256=expected_target_artifact_sha256,
            expected_verification_manifest_sha256=expected_verification_manifest_sha256,
        ),
    )
