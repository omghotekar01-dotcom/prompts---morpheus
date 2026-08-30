from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from benchmark.reproduction_pack import (
    REQUIRED_ARTIFACTS,
    ReproductionPackError,
    verify_reproduction_pack,
)


def _write_pack(root: Path, *, revision: str = "a" * 40) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for index, name in enumerate(REQUIRED_ARTIFACTS):
        payload = f"artifact-{index}-{name}\n".encode("utf-8")
        path = root / name
        path.write_bytes(payload)
        hashes[name] = sha256(payload).hexdigest()

    manifest = {"source_revision": revision, "artifacts": hashes}
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return hashes


def test_valid_pack_is_deterministic_and_revision_bound(tmp_path: Path) -> None:
    hashes = _write_pack(tmp_path)

    first = verify_reproduction_pack(tmp_path)
    second = verify_reproduction_pack(tmp_path)

    assert first.source_revision == "a" * 40
    assert dict(first.artifact_hashes) == hashes
    assert first.pack_sha256 == second.pack_sha256
    assert len(first.pack_sha256) == 64


def test_tampered_artifact_is_rejected(tmp_path: Path) -> None:
    _write_pack(tmp_path)
    (tmp_path / "results.json").write_text("tampered", encoding="utf-8")

    with pytest.raises(ReproductionPackError, match="SHA-256 mismatch"):
        verify_reproduction_pack(tmp_path)


def test_missing_required_declaration_is_rejected(tmp_path: Path) -> None:
    _write_pack(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"].pop("commands.txt")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ReproductionPackError, match="missing required artifact declarations"):
        verify_reproduction_pack(tmp_path)


def test_path_traversal_is_rejected_even_when_declared_hash_is_well_formed(tmp_path: Path) -> None:
    _write_pack(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["../escape.txt"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ReproductionPackError, match="escapes pack root"):
        verify_reproduction_pack(tmp_path)


def test_short_or_non_hex_revision_is_rejected(tmp_path: Path) -> None:
    _write_pack(tmp_path, revision="deadbeef")

    with pytest.raises(ReproductionPackError, match="full 40-character git SHA"):
        verify_reproduction_pack(tmp_path)
