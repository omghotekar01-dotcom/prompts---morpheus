from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .pilot_startup_evidence_handoff_replay_catalog import (
    ReplayDescriptorContext,
    verify_pilot_startup_evidence_handoff_replay_catalog,
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def _catalog_path(store_dir: Path, digest: str) -> Path:
    if _HEX64.fullmatch(digest) is None:
        raise ValueError("invalid replay catalog digest")
    return store_dir / f"{digest}.json"


def persist_pilot_startup_evidence_handoff_replay_catalog(
    store_dir: str | Path,
    catalog: Mapping[str, Any],
    contexts: Sequence[ReplayDescriptorContext],
) -> Path:
    """Persist one freshly verified replay-descriptor catalog under its content identity.

    Persistence supplies deterministic local audit continuity only. It does not establish a digital
    signature, trusted timestamp or chronology, signer/operator identity, external attestation,
    externally append-only publication, production authorization, security certification,
    benchmark/performance evidence, novelty evidence, or patentability evidence.
    """

    if not verify_pilot_startup_evidence_handoff_replay_catalog(catalog, contexts):
        raise ValueError("transported replay-descriptor catalog failed verification")

    digest = catalog.get("replay_catalog_sha256")
    if not isinstance(digest, str):
        raise ValueError("replay catalog digest is missing")

    root = Path(store_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = _catalog_path(root, digest)
    canonical = _canonical_json_bytes(catalog)

    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        existing = path.read_bytes()
        if existing != canonical:
            raise ValueError("replay catalog digest collision or on-disk tampering detected")
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


def load_pilot_startup_evidence_handoff_replay_catalog(
    path: str | Path,
    contexts: Sequence[ReplayDescriptorContext],
) -> dict[str, Any]:
    """Load canonical content-addressed catalog bytes and freshly re-verify every descriptor context."""

    target = Path(path)
    match = re.fullmatch(r"([0-9a-f]{64})\.json", target.name)
    if match is None:
        raise ValueError("replay catalog filename is not content-addressed")
    expected_digest = match.group(1)

    raw = target.read_bytes()
    try:
        catalog = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("stored replay catalog is not valid UTF-8 JSON") from exc
    if not isinstance(catalog, dict):
        raise ValueError("stored replay catalog must be a JSON object")
    if raw != _canonical_json_bytes(catalog):
        raise ValueError("stored replay catalog is not canonical JSON")
    if catalog.get("replay_catalog_sha256") != expected_digest:
        raise ValueError("stored replay catalog filename/digest mismatch")
    if not verify_pilot_startup_evidence_handoff_replay_catalog(catalog, contexts):
        raise ValueError("stored replay catalog failed fresh semantic verification")

    return catalog
