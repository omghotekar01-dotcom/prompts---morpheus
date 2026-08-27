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


def test_evidence_package_verifies_hashes_and_is_deterministic(tmp_path: Path) -> None:
    header = _artifact(tmp_path / "generated.hpp", "generated_header", VALID_GENERATED_HEADER)
    descriptor = {
        "version": "0.10.0-rc1",
        "commit": COMMIT,
        "artifacts": [header],
        "claims": [
            {
                "type": "generated_cpp20",
                "text": "MORPHEUS generated the attached C++20 header.",
                "evidence_roles": ["generated_header"],
            }
        ],
    }

    first_zip = tmp_path / "first.zip"
    second_zip = tmp_path / "second.zip"
    first = build_evidence_package(descriptor, tmp_path / "pkg-a", zip_output=first_zip)
    second = build_evidence_package(descriptor, tmp_path / "pkg-b", zip_output=second_zip)

    assert first["manifest"]["release_state"] == "CLAIMS_EVIDENCE_COMPLETE"
    assert first["manifest"]["schema"] == "morpheus-release-manifest-v2"
    assert first["package_index"]["release_manifest_sha256"] == second["package_index"]["release_manifest_sha256"]
    assert hashlib.sha256(first_zip.read_bytes()).hexdigest() == hashlib.sha256(second_zip.read_bytes()).hexdigest()
    assert (tmp_path / "pkg-a" / "evidence-index.json").is_file()
    assert (tmp_path / "pkg-a" / "evidence").is_dir()


def test_evidence_package_rejects_declared_hash_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "raw.json"
    path.write_text("{}", encoding="utf-8")
    descriptor = {
        "version": "0.10.0-rc1",
        "commit": COMMIT,
        "artifacts": [{"role": "raw_measurements", "path": str(path), "sha256": "0" * 64}],
        "claims": [],
    }
    with pytest.raises(ValueError, match="hash mismatch"):
        build_evidence_package(descriptor, tmp_path / "package")


def test_evidence_package_preserves_blocked_claim_state(tmp_path: Path) -> None:
    header = _artifact(tmp_path / "generated.hpp", "generated_header", VALID_GENERATED_HEADER)
    descriptor = {
        "version": "0.10.0-rc1",
        "commit": COMMIT,
        "artifacts": [header],
        "claims": [
            {
                "type": "measured_speedup",
                "text": "This claim must remain blocked without benchmark evidence.",
                "evidence_roles": [
                    "experiment_manifest",
                    "raw_measurements",
                    "statistical_summary",
                    "machine_profile",
                    "baseline_manifest",
                ],
            }
        ],
    }
    result = build_evidence_package(descriptor, tmp_path / "package")
    assert result["manifest"]["release_state"] == "BLOCKED_BY_CLAIM_EVIDENCE"
    missing = result["manifest"]["claim_gate"]["decisions"][0]["missing_roles"]
    assert "raw_measurements" in missing
    assert "statistical_summary" in missing
    assert "raw_measurements" in result["manifest"]["claims"][0]["declared_roles_missing_from_artifacts"]
