from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .pilot_startup_evidence_checkpoint_transition_chain_extension_chain import ExtensionEvidence
from .pilot_startup_evidence_handoff_replay_descriptor import (
    verify_pilot_startup_evidence_handoff_replay_descriptor,
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def _descriptor_path(store_dir: Path, digest: str) -> Path:
    if _HEX64.fullmatch(digest) is None:
        raise ValueError("invalid replay descriptor digest")
    return store_dir / f"{digest}.json"


def persist_pilot_startup_evidence_handoff_replay_descriptor(
    store_dir: str | Path,
    descriptor: Mapping[str, Any],
    receipt_path: str | Path,
    bundle_dir: str | Path,
    manifest: Mapping[str, Any],
    extension_chain: Mapping[str, Any],
    evidence: Sequence[ExtensionEvidence],
) -> Path:
    """Persist one freshly verified replay descriptor under its content identity.

    Persistence provides local immutable audit continuity only. It does not turn the descriptor into
    a signature, trusted timestamp, signer/operator identity, external attestation, externally
    append-only publication, production authorization, security certification, benchmark evidence,
    novelty evidence, or patent evidence.
    """

    if not verify_pilot_startup_evidence_handoff_replay_descriptor(
        descriptor, receipt_path, bundle_dir, manifest, extension_chain, evidence
    ):
        raise ValueError("transported startup-evidence replay descriptor failed verification")

    digest = descriptor.get("replay_descriptor_sha256")
    if not isinstance(digest, str):
        raise ValueError("replay descriptor digest is missing")

    root = Path(store_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = _descriptor_path(root, digest)
    canonical = _canonical_json_bytes(descriptor)

    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        existing = path.read_bytes()
        if existing != canonical:
            raise ValueError("replay descriptor digest collision or on-disk tampering detected")
        return path

    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink(missing_ok=True)
        finally:
            raise

    return path


def load_pilot_startup_evidence_handoff_replay_descriptor(
    path: str | Path,
    receipt_path: str | Path,
    bundle_dir: str | Path,
    manifest: Mapping[str, Any],
    extension_chain: Mapping[str, Any],
    evidence: Sequence[ExtensionEvidence],
) -> dict[str, Any]:
    """Load a canonical content-addressed descriptor and freshly re-verify its replay dependency."""

    target = Path(path)
    match = re.fullmatch(r"([0-9a-f]{64})\.json", target.name)
    if match is None:
        raise ValueError("replay descriptor filename is not content-addressed")
    expected_digest = match.group(1)

    raw = target.read_bytes()
    try:
        descriptor = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("stored replay descriptor is not valid UTF-8 JSON") from exc
    if not isinstance(descriptor, dict):
        raise ValueError("stored replay descriptor must be a JSON object")
    if raw != _canonical_json_bytes(descriptor):
        raise ValueError("stored replay descriptor is not canonical JSON")
    if descriptor.get("replay_descriptor_sha256") != expected_digest:
        raise ValueError("stored replay descriptor filename/digest mismatch")
    if not verify_pilot_startup_evidence_handoff_replay_descriptor(
        descriptor, receipt_path, bundle_dir, manifest, extension_chain, evidence
    ):
        raise ValueError("stored replay descriptor failed fresh semantic verification")

    return descriptor
