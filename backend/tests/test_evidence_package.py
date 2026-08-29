from __future__ import annotations

import hashlib
import json
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


def test_distribution_calibration_package_links_manifest_raw_and_machine(tmp_path: Path) -> None:
    machine_payload = {
        "protocol": "morpheus-machine-profile-v1",
        "platform": {"system": "test", "machine": "x86_64"},
    }
    machine_bytes = (json.dumps(machine_payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    machine = _artifact(tmp_path / "machine.json", "machine_profile", machine_bytes)

    raw_payload = {
        "profile_id": "local-dist-1337",
        "schema_version": 4,
        "evidence_state": "MEASURED_LOCAL_PROCESS_REPEATED_IMPLEMENTATION_AND_DISTRIBUTION_BOUND",
        "protocol": "morpheus-distribution-calibration-v1",
        "distribution_protocol": "morpheus-access-distribution-v1",
        "n": 1000,
        "operations": 5000,
        "seed": 1337,
        "measurements": [
            {
                "primitive": "robin_hood_hash",
                "implementation_id": "morpheus.RobinHoodHashIndex.v1",
                "operation": "point_lookup",
                "access_distribution": {"kind": "uniform"},
                "ns_per_op": 42.0,
                "repetitions": 5,
            }
        ],
    }
    raw_bytes = (json.dumps(raw_payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    raw = _artifact(tmp_path / "raw.json", "raw_measurements", raw_bytes)

    manifest_payload = {
        "schema_version": 1,
        "protocol": "morpheus-distribution-calibration-matrix-v1",
        "distribution_protocol": "morpheus-access-distribution-v1",
        "source_commit": COMMIT,
        "executable_sha256": "b" * 64,
        "machine_profile_sha256": machine["sha256"],
        "machine_fingerprint_sha256": "c" * 64,
        "distributions": ["uniform"],
        "implementation_ids": ["morpheus.RobinHoodHashIndex.v1"],
        "runs": [
            {
                "sha256": raw["sha256"],
                "record_count": 1000,
                "operations": 5000,
                "distributions": ["uniform"],
            }
        ],
        "evidence_state": "CONTENT_HASHED_DISTRIBUTION_BOUND_PRIMITIVE_CALIBRATION_MATRIX",
    }
    manifest_bytes = (json.dumps(manifest_payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    calibration_manifest = _artifact(
        tmp_path / "distribution-manifest.json",
        "distribution_calibration_manifest",
        manifest_bytes,
    )

    descriptor = {
        "version": "0.10.0-rc1",
        "commit": COMMIT,
        "artifacts": [machine, raw, calibration_manifest],
        "claims": [
            {
                "type": "distribution_calibration_evidence",
                "text": "The package contains distribution-bound primitive calibration evidence.",
                "evidence_roles": [
                    "distribution_calibration_manifest",
                    "raw_measurements",
                    "machine_profile",
                ],
            }
        ],
    }
    result = build_evidence_package(descriptor, tmp_path / "distribution-package")
    assert result["manifest"]["release_state"] == "CLAIMS_EVIDENCE_COMPLETE"
    assert result["package_index"]["cross_artifact_validation"] == "PASSED"
    assert result["manifest"]["claim_gate"]["decisions"][0]["allowed"] is True

    bad_manifest = dict(manifest_payload)
    bad_manifest["machine_profile_sha256"] = "0" * 64
    bad_manifest_bytes = (json.dumps(bad_manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
    bad_artifact = _artifact(
        tmp_path / "bad-distribution-manifest.json",
        "distribution_calibration_manifest",
        bad_manifest_bytes,
    )
    bad_descriptor = {**descriptor, "artifacts": [machine, raw, bad_artifact]}
    with pytest.raises(ValueError, match="machine_profile_sha256"):
        build_evidence_package(bad_descriptor, tmp_path / "bad-distribution-package")


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
