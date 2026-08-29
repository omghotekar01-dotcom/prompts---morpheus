from __future__ import annotations

import json

from app.evidence_validation import validate_cross_artifact_links, validate_evidence_bytes


def test_structural_validator_accepts_frozen_experiment_manifest() -> None:
    payload = {
        "schema": "morpheus-experiment-manifest-v1",
        "experiments": [{"experiment_id": "mx-1"}],
    }
    result = validate_evidence_bytes("experiment_manifest", json.dumps(payload).encode())
    assert result.valid is True
    assert result.evidence_state == "EVIDENCE_STRUCTURAL_VALIDATION_PASSED"


def test_structural_validator_rejects_failed_full_verification_manifest() -> None:
    payload = {
        "schema": "morpheus-artifact-verification-v2",
        "success": False,
        "compile_gate": {},
        "behavior_gate": {},
    }
    result = validate_evidence_bytes("full_artifact_verification_manifest", json.dumps(payload).encode())
    assert result.valid is False
    assert "success=true" in result.details[0]


def test_generated_header_requires_codegen_markers() -> None:
    good = b"#pragma once\nnamespace morpheus { class GeneratedIndex {}; }\n"
    bad = b"int unrelated = 1;\n"
    assert validate_evidence_bytes("generated_header", good).valid is True
    assert validate_evidence_bytes("generated_header", bad).valid is False


def _distribution_raw() -> dict[str, object]:
    return {
        "profile_id": "local-dist-1",
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
                "access_distribution": {
                    "kind": "hotspot",
                    "hotspot_fraction": 0.1,
                    "hotspot_probability": 0.8,
                },
                "ns_per_op": 40.0,
                "repetitions": 5,
            }
        ],
    }


def test_distribution_raw_measurements_require_exact_distribution_identity() -> None:
    good = validate_evidence_bytes("raw_measurements", json.dumps(_distribution_raw()).encode())
    assert good.valid is True

    bad_payload = _distribution_raw()
    measurement = bad_payload["measurements"][0]
    assert isinstance(measurement, dict)
    measurement["access_distribution"] = {"kind": "hotspot", "hotspot_fraction": 0.1}
    bad = validate_evidence_bytes("raw_measurements", json.dumps(bad_payload).encode())
    assert bad.valid is False
    assert any("hotspot_probability" in detail for detail in bad.details)


def test_distribution_calibration_manifest_requires_hashes_commit_and_runs() -> None:
    payload = {
        "schema_version": 1,
        "protocol": "morpheus-distribution-calibration-matrix-v1",
        "distribution_protocol": "morpheus-access-distribution-v1",
        "source_commit": "a" * 40,
        "executable_sha256": "b" * 64,
        "machine_profile_sha256": "c" * 64,
        "machine_fingerprint_sha256": "d" * 64,
        "distributions": ["hotspot", "uniform"],
        "implementation_ids": ["morpheus.RobinHoodHashIndex.v1"],
        "runs": [
            {
                "sha256": "e" * 64,
                "record_count": 1000,
                "operations": 5000,
                "distributions": ["hotspot", "uniform"],
            }
        ],
        "evidence_state": "CONTENT_HASHED_DISTRIBUTION_BOUND_PRIMITIVE_CALIBRATION_MATRIX",
    }
    good = validate_evidence_bytes("distribution_calibration_manifest", json.dumps(payload).encode())
    assert good.valid is True

    payload["source_commit"] = "not-a-commit"
    bad = validate_evidence_bytes("distribution_calibration_manifest", json.dumps(payload).encode())
    assert bad.valid is False
    assert any("source_commit" in detail for detail in bad.details)


def test_cross_artifact_link_detects_statistics_raw_hash_mismatch() -> None:
    errors = validate_cross_artifact_links(
        {
            "raw_measurements": {"canonical_json_sha256": "a" * 64},
            "statistical_summary": {
                "json": {"source_raw_measurements_sha256": "b" * 64},
            },
        }
    )
    assert errors and "does not match" in errors[-1]


def test_standard_baseline_statistics_reject_nonbaseline_raw_protocol() -> None:
    errors = validate_cross_artifact_links(
        {
            "raw_measurements": {
                "canonical_json_sha256": "a" * 64,
                "json": {"protocol": "morpheus-distribution-calibration-v1"},
            },
            "statistical_summary": {
                "json": {"source_raw_measurements_sha256": "a" * 64},
            },
        }
    )
    assert any("requires raw_measurements protocol morpheus-standard-baseline-matrix-v1" in error for error in errors)


def test_distribution_manifest_links_machine_and_raw_bytes() -> None:
    raw_hash = "e" * 64
    errors = validate_cross_artifact_links(
        {
            "machine_profile": {"sha256": "c" * 64},
            "raw_measurements": {
                "sha256": raw_hash,
                "json": {"protocol": "morpheus-distribution-calibration-v1"},
            },
            "distribution_calibration_manifest": {
                "json": {
                    "machine_profile_sha256": "c" * 64,
                    "runs": [{"sha256": raw_hash}],
                }
            },
        }
    )
    assert errors == []

    bad = validate_cross_artifact_links(
        {
            "machine_profile": {"sha256": "0" * 64},
            "raw_measurements": {
                "sha256": raw_hash,
                "json": {"protocol": "morpheus-distribution-calibration-v1"},
            },
            "distribution_calibration_manifest": {
                "json": {
                    "machine_profile_sha256": "c" * 64,
                    "runs": [{"sha256": "f" * 64}],
                }
            },
        }
    )
    assert any("machine_profile_sha256" in error for error in bad)
    assert any("not referenced" in error for error in bad)
