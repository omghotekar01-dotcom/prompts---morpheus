from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.generated_migration_evidence import ROLE
from app.release_evidence_validation import validate_release_evidence_bytes
from release.evidence_package import build_evidence_package


COMMIT = "a" * 40


def _payload() -> dict[str, object]:
    return {
        "schema": "morpheus-generated-migration-verification-v1",
        "success": True,
        "evidence_state": "COMPILE_AND_EXECUTION_VERIFIED_LOCAL_GENERATED_MIGRATION",
        "source_candidate_id": "cfg-source",
        "target_candidate_id": "cfg-target",
        "source_manifest_sha256": "1" * 64,
        "target_manifest_sha256": "2" * 64,
        "harness_sha256": "3" * 64,
        "compiler": "/toolchain/cxx",
        "compiler_kind": "gnu",
        "compiler_version": "test compiler 1.0",
        "compile_returncode": 0,
        "run_returncode": 0,
        "source_reads": 501,
        "target_reads": 277,
        "invalid_reads": 0,
        "final_generation": 4,
        "compile_stdout": "",
        "compile_stderr": "",
        "run_stdout": (
            "MORPHEUS_GENERATED_MIGRATION_OK source_reads=501 target_reads=277 "
            "invalid_reads=0 final_generation=4\n"
        ),
        "run_stderr": "",
        "truth_boundary": "same-process generated migration only",
    }


def _bytes(payload: dict[str, object]) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def test_generated_migration_release_role_requires_strict_verified_structure() -> None:
    valid = validate_release_evidence_bytes(ROLE, _bytes(_payload()))
    assert valid.valid is True
    assert valid.evidence_state == "EVIDENCE_STRUCTURAL_VALIDATION_PASSED"

    broken = _payload()
    broken["invalid_reads"] = 1
    broken["run_stdout"] = "MORPHEUS_GENERATED_MIGRATION_OK invalid_reads=1"
    invalid = validate_release_evidence_bytes(ROLE, _bytes(broken))
    assert invalid.valid is False
    assert any("invalid_reads" in detail for detail in invalid.details)


def test_evidence_package_can_authorize_only_narrow_generated_migration_claim(tmp_path: Path) -> None:
    data = _bytes(_payload())
    path = tmp_path / "generated-migration-verification.json"
    path.write_bytes(data)
    artifact = {
        "role": ROLE,
        "path": str(path),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    descriptor = {
        "version": "0.11.0-evolution",
        "commit": COMMIT,
        "artifacts": [artifact],
        "claims": [
            {
                "type": "same_process_generated_migration",
                "text": "This package demonstrates the declared same-process generated migration harness.",
                "evidence_roles": [ROLE],
            }
        ],
    }
    result = build_evidence_package(descriptor, tmp_path / "package")
    assert result["manifest"]["release_state"] == "CLAIMS_EVIDENCE_COMPLETE"
    decision = result["manifest"]["claim_gate"]["decisions"][0]
    assert decision["claim_type"] == "same_process_generated_migration"
    assert decision["allowed"] is True
    packaged = result["package_index"]["files"][0]
    assert packaged["role"] == ROLE
    assert packaged["structural_validation"]["valid"] is True


def test_evidence_package_rejects_forged_generated_migration_success(tmp_path: Path) -> None:
    broken = _payload()
    broken["target_candidate_id"] = broken["source_candidate_id"]
    broken["compile_returncode"] = 1
    data = _bytes(broken)
    path = tmp_path / "forged.json"
    path.write_bytes(data)
    descriptor = {
        "version": "0.11.0-evolution",
        "commit": COMMIT,
        "artifacts": [
            {
                "role": ROLE,
                "path": str(path),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        ],
        "claims": [
            {
                "type": "same_process_generated_migration",
                "text": "forged",
                "evidence_roles": [ROLE],
            }
        ],
    }
    with pytest.raises(ValueError, match="structural validation failed"):
        build_evidence_package(descriptor, tmp_path / "rejected-package")
