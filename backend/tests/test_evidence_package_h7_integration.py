from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from release.evidence_package import build_evidence_package


COMMIT = "a" * 40
VALID_GENERATED_HEADER = b"#pragma once\nnamespace morpheus { class GeneratedIndex {}; }\n"


def _artifact(path: Path, role: str, content: bytes) -> dict[str, str]:
    path.write_bytes(content)
    return {"role": role, "path": str(path), "sha256": hashlib.sha256(content).hexdigest()}


def test_release_package_rejects_duplicate_evidence_roles(tmp_path: Path) -> None:
    first = _artifact(tmp_path / "first.hpp", "generated_header", VALID_GENERATED_HEADER)
    second = _artifact(tmp_path / "second.hpp", "generated_header", VALID_GENERATED_HEADER)
    descriptor = {
        "version": "0.10.0-rc1",
        "commit": COMMIT,
        "artifacts": [first, second],
        "claims": [],
    }

    with pytest.raises(ValueError, match="duplicate evidence artifact role"):
        build_evidence_package(descriptor, tmp_path / "package")


def test_release_package_invokes_h7_cross_artifact_validator(monkeypatch, tmp_path: Path) -> None:
    header = _artifact(tmp_path / "generated.hpp", "generated_header", VALID_GENERATED_HEADER)
    observed: dict[str, object] = {}

    def fail_h7(context):
        observed["roles"] = sorted(context)
        return ["sentinel H7 chain mismatch"]

    monkeypatch.setattr("release.evidence_package.validate_rq7_confirmatory_cross_links", fail_h7)
    descriptor = {
        "version": "0.10.0-rc1",
        "commit": COMMIT,
        "artifacts": [header],
        "claims": [],
    }

    with pytest.raises(ValueError, match="sentinel H7 chain mismatch"):
        build_evidence_package(descriptor, tmp_path / "package")
    assert observed["roles"] == ["generated_header"]
