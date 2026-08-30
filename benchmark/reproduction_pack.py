"""Deterministic validation for MORPHEUS independent-reproduction packs.

The validator intentionally uses only the Python standard library so an external
reviewer can run it without installing the MORPHEUS service stack.  It checks
that a reproduction bundle is complete, content-addressed, and tied to one
source revision before benchmark claims are compared.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable, Mapping

REQUIRED_ARTIFACTS = (
    "environment.json",
    "machine-profile.json",
    "workload-manifest.json",
    "results.json",
    "commands.txt",
)


class ReproductionPackError(ValueError):
    """Raised when a reproduction pack is incomplete or internally inconsistent."""


@dataclass(frozen=True)
class VerifiedReproductionPack:
    root: Path
    source_revision: str
    artifact_hashes: Mapping[str, str]
    pack_sha256: str


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_pack_digest(source_revision: str, artifact_hashes: Mapping[str, str]) -> str:
    payload = {
        "source_revision": source_revision,
        "artifacts": dict(sorted(artifact_hashes.items())),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def _validate_revision(value: object) -> str:
    if not isinstance(value, str):
        raise ReproductionPackError("source_revision must be a string")
    normalized = value.strip().lower()
    if len(normalized) != 40 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise ReproductionPackError("source_revision must be a full 40-character git SHA")
    return normalized


def verify_reproduction_pack(
    root: str | Path,
    *,
    required_artifacts: Iterable[str] = REQUIRED_ARTIFACTS,
) -> VerifiedReproductionPack:
    """Validate and content-address an external reproduction directory.

    ``manifest.json`` must contain ``source_revision`` and an ``artifacts``
    object mapping every required file name to its SHA-256.  Extra artifact
    entries are permitted but are verified too, preventing a reviewer from
    accidentally publishing a manifest that does not match the shared files.
    """

    root_path = Path(root)
    manifest_path = root_path / "manifest.json"
    if not manifest_path.is_file():
        raise ReproductionPackError("manifest.json is required")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReproductionPackError(f"invalid manifest.json: {exc}") from exc

    if not isinstance(manifest, dict):
        raise ReproductionPackError("manifest.json must contain a JSON object")

    source_revision = _validate_revision(manifest.get("source_revision"))
    declared = manifest.get("artifacts")
    if not isinstance(declared, dict) or not declared:
        raise ReproductionPackError("manifest artifacts must be a non-empty object")

    required = tuple(required_artifacts)
    missing = sorted(set(required) - set(declared))
    if missing:
        raise ReproductionPackError(f"missing required artifact declarations: {', '.join(missing)}")

    verified: dict[str, str] = {}
    for relative_name, expected_hash in sorted(declared.items()):
        if not isinstance(relative_name, str) or not relative_name or Path(relative_name).is_absolute():
            raise ReproductionPackError("artifact paths must be non-empty relative paths")
        if ".." in Path(relative_name).parts:
            raise ReproductionPackError(f"artifact path escapes pack root: {relative_name}")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64 or any(
            ch not in "0123456789abcdefABCDEF" for ch in expected_hash
        ):
            raise ReproductionPackError(f"invalid SHA-256 for {relative_name}")

        artifact_path = root_path / relative_name
        if not artifact_path.is_file():
            raise ReproductionPackError(f"declared artifact is missing: {relative_name}")
        actual_hash = _file_sha256(artifact_path)
        if actual_hash != expected_hash.lower():
            raise ReproductionPackError(f"SHA-256 mismatch for {relative_name}")
        verified[relative_name] = actual_hash

    pack_sha256 = _canonical_pack_digest(source_revision, verified)
    return VerifiedReproductionPack(
        root=root_path,
        source_revision=source_revision,
        artifact_hashes=verified,
        pack_sha256=pack_sha256,
    )
